import importlib.util
import json
import logging
import os
import sys
import asyncio
import platform
import re
from typing import Callable, Iterable, Any, Tuple, Optional
from aiohttp import web
import traceback

from opentelemetry import trace
from opentelemetry.propagate import extract, inject

from agentuity.otel import init
from agentuity.instrument import instrument
from agentuity import __version__

from .data import Data
from .context import AgentContext
from .request import AgentRequest
from .response import AgentResponse
from .keyvalue import KeyValueStore
from .vector import VectorStore
from .objectstore import ObjectStore
from .data import dataLikeToData

logger = logging.getLogger(__name__)
port = int(os.environ.get("AGENTUITY_CLOUD_PORT", os.environ.get("PORT", 3500)))


def safe_python_name(name: str) -> str:
    begins_with_number = re.compile(r"^\d+")
    safe_python_name_transformer = re.compile(r"[^0-9a-zA-Z_]")
    remove_starting_dashes = re.compile(r"^-+")
    remove_ending_dashes = re.compile(r"-+$")

    if begins_with_number.match(name):
        name = begins_with_number.sub("", name)
    name = safe_python_name_transformer.sub("_", name)
    if remove_starting_dashes.match(name):
        name = remove_starting_dashes.sub("", name)
    if remove_ending_dashes.search(name):
        name = remove_ending_dashes.sub("", name)
    return name


# Utility function to inject trace context into response headers
def inject_trace_context(headers):
    """Inject trace context into response headers using configured propagators."""
    try:
        inject(headers)
    except Exception as e:
        # Log the error but don't fail the request
        logger.error(f"Error injecting trace context: {e}")


def load_agent_module(agent_id: str, name: str, filename: str):
    # Load the agent module dynamically
    logger.debug(f"loading agent {agent_id} ({name}) from {filename}")
    spec = importlib.util.spec_from_file_location(agent_id, filename)
    if spec is None:
        raise ImportError(f"Could not load module for {filename}")

    agent_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_module)

    # Check if the module has a run function
    if not hasattr(agent_module, "run"):
        raise AttributeError(f"Module {filename} does not have a run function")

    # Check if the module has an welcome function - which is optional
    welcome = None
    if hasattr(agent_module, "welcome"):
        welcome = agent_module.welcome

    logger.debug(f"Loaded agent: {agent_id}")

    return {
        "id": agent_id,
        "name": name,
        "run": agent_module.run,
        "welcome": welcome,
    }


async def run_agent(
    tracer, agentId, agent, agent_request, agent_response, agent_context
):
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute("@agentuity/agentId", agentId)
        span.set_attribute("@agentuity/agentName", agent["name"])
        try:
            result = await agent["run"](
                request=agent_request,
                response=agent_response,
                context=agent_context,
            )

            span.set_status(trace.Status(trace.StatusCode.OK))
            return result

        except Exception as e:
            span.record_exception(e)
            span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
            logger.error(f"Agent execution failed: {str(e)}")
            raise e


def isBase64Content(val: Any) -> bool:
    if isinstance(val, str):
        return (
            re.match(
                r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$", val
            )
            is not None
        )
    return False


async def encode_welcome(val):
    if isinstance(val, dict):
        if "prompts" in val:
            for prompt in val["prompts"]:
                if "data" in prompt:
                    if not isBase64Content(prompt["data"]):
                        data = dataLikeToData(
                            prompt["data"],
                            prompt.get("contentType", "text/plain"),
                        )
                        ct = data.content_type
                        if (
                            "text/" in ct
                            or "json" in ct
                            or "image" in ct
                            or "audio" in ct
                            or "video" in ct
                        ):
                            prompt["data"] = await data.base64()
                        else:
                            prompt["data"] = await data.text()
                        prompt["contentType"] = ct
        else:
            for key, value in val.items():
                val[key] = await encode_welcome(value)
    return val


async def handle_welcome_request(request: web.Request):
    res = {}
    for agent in request.app["agents_by_id"].values():
        if "welcome" in agent and agent["welcome"] is not None:
            fn = agent["welcome"]()
            if isinstance(fn, dict):
                res[agent["id"]] = await encode_welcome(fn)
            else:
                res[agent["id"]] = await encode_welcome(await fn)
    return web.json_response(res)


async def handle_agent_welcome_request(request: web.Request):
    agents_by_id = request.app["agents_by_id"]
    if request.match_info["agent_id"] in agents_by_id:
        agent = agents_by_id[request.match_info["agent_id"]]
        if "welcome" in agent and agent["welcome"] is not None:
            fn = agent["welcome"]()
            if not isinstance(fn, dict):
                fn = await encode_welcome(await fn)
            return web.json_response(fn)
        else:
            return web.Response(
                status=404,
                content_type="text/plain",
            )
    else:
        return web.Response(
            text=f"Agent {request.match_info['agent_id']} not found",
            status=404,
            content_type="text/plain",
        )


def make_response_headers(
    request: web.Request,
    contentType: str,
    metadata: dict = None,
    additional: dict = None,
):
    headers = {}
    inject_trace_context(headers)
    headers["Content-Type"] = contentType
    headers["Server"] = "Agentuity Python SDK/" + __version__
    origin = request.headers.get("origin") or request.headers.get("Origin")
    if origin:
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Methods"] = (
            "GET, PUT, DELETE, PATCH, OPTIONS, POST"
        )
        headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    if metadata is not None:
        for key, value in metadata.items():
            headers[f"x-agentuity-{key}"] = str(value)
    if additional is not None:
        for key, value in additional.items():
            headers[key] = value
    return headers


async def stream_response(
    request: web.Request, iterable: Iterable[Any], contentType: str, metadata: dict = {}
):
    headers = make_response_headers(request, contentType, metadata)
    resp = web.StreamResponse(headers=headers)

    try:
        await resp.prepare(request)
    except Exception as e:
        error_msg = str(e)
        if (
            "closing transport" in error_msg.lower()
            or "connection reset" in error_msg.lower()
        ):
            # Client has already disconnected, log and return early
            logger.warning(
                f"Client disconnected before response could be prepared: {error_msg}"
            )
            # Return a simple response that won't try to write to the closed connection
            return web.Response(status=499, text="Client disconnected")
        else:
            logger.error(f"Failed to prepare response: {e}")
            return web.Response(
                text="Connection error",
                status=500,
                headers=make_response_headers(request, "text/plain"),
            )

    try:
        if hasattr(iterable, "__anext__"):
            # Handle async iterators
            async for chunk in iterable:
                if chunk is not None:
                    # If chunk is a StreamReader, read from it to get bytes
                    if hasattr(chunk, "read"):
                        data = await chunk.read()
                        if data:
                            await resp.write(data)
                    else:
                        await resp.write(chunk)
        else:
            # Handle regular iterators
            for chunk in iterable:
                if chunk is not None:
                    # If chunk is a StreamReader, read from it to get bytes
                    if hasattr(chunk, "read"):
                        data = await chunk.read()
                        if data:
                            await resp.write(data)
                    else:
                        await resp.write(chunk)

        await resp.write_eof()
    except Exception as e:
        error_msg = str(e)
        if (
            "closing transport" in error_msg.lower()
            or "connection reset" in error_msg.lower()
        ):
            # Client disconnected during streaming, log but don't try to write more
            logger.warning(f"Client disconnected during streaming: {error_msg}")
        else:
            logger.error(f"Error during streaming response: {e}")
            # Don't try to write more if connection is already closed
            if "closing transport" not in error_msg.lower():
                try:
                    await resp.write_eof()
                except (ConnectionError, OSError, RuntimeError):
                    pass

    return resp


async def handle_agent_options_request(request: web.Request):
    return web.Response(
        headers=make_response_headers(request, "text/plain"),
        text="OK",
    )


def safe_parse_if_looks_like_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        if value.startswith("{") and value.endswith("}"):
            return json.loads(value)
        elif value.startswith("[") and value.endswith("]"):
            return json.loads(value)
        else:
            return value
    except json.JSONDecodeError:
        return value


base_url = os.environ.get("AGENTUITY_TRANSPORT_URL", "https://agentuity.ai")
api_key = os.environ.get("AGENTUITY_SDK_KEY") or os.environ.get("AGENTUITY_API_KEY")


async def handle_agent_request(request: web.Request):
    # Access the agents_by_id from the app state
    agents_by_id = request.app["agents_by_id"]

    agentId = request.match_info["agent_id"]
    logger.debug(f"request: {request.method} {request.path}")

    # Check if the agent exists in our map
    if agentId in agents_by_id:
        agent = agents_by_id[agentId]
        tracer = trace.get_tracer("http-server")

        # Extract trace context from headers -- these MUST be lowercase for the propagator to work
        headers = dict()
        for k, v in request.headers.items():
            headers[k.lower()] = v
        context = extract(carrier=headers)

        with tracer.start_as_current_span(
            f"HTTP {request.method}",
            context=context,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": request.method,
                "http.url": str(request.url),
                "http.host": request.host,
                "http.user_agent": headers.get("user-agent"),
                "http.path": request.path,
                "@agentuity/agentId": agentId,
                "@agentuity/agentName": agent["name"],
            },
        ) as span:
            try:
                trigger = headers.get("x-agentuity-trigger", "manual")
                contentType = headers.get("content-type", "application/octet-stream")
                metadata = {}
                scope = "local"
                if span.is_recording():
                    run_id = span.get_span_context().trace_id
                else:
                    run_id = None
                for key, value in headers.items():
                    if key.startswith("x-agentuity-") and key != "x-agentuity-trigger":
                        if key == "x-agentuity-run-id":
                            run_id = value
                        elif key == "x-agentuity-scope":
                            scope = value
                        elif key == "x-agentuity-headers":
                            try:
                                headers = json.loads(value)
                                kv = {}
                                if (
                                    "content-type" in headers
                                    and headers["content-type"] is not None
                                ):
                                    kv["content-type"] = headers["content-type"]
                                for k, v in headers.items():
                                    if k == "x-agentuity-metadata":
                                        try:
                                            md = json.loads(v)
                                            if "scope" in metadata:
                                                scope = md["scope"]
                                                del md["scope"]
                                            for k, v in md.items():
                                                metadata[k] = (
                                                    safe_parse_if_looks_like_json(v)
                                                )
                                        except json.JSONDecodeError:
                                            logger.error(
                                                f"Error parsing x-agentuity-metadata: {v}"
                                            )
                                        continue
                                    if k.startswith("x-agentuity-"):
                                        metadata[k[12:]] = (
                                            safe_parse_if_looks_like_json(v)
                                        )
                                    else:
                                        kv[k] = safe_parse_if_looks_like_json(v)
                                metadata["headers"] = kv
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Error parsing x-agentuity-headers: {value}"
                                )
                                metadata["headers"] = value
                        elif key == "x-agentuity-metadata":
                            try:
                                md = json.loads(value)
                                if "scope" in metadata:
                                    scope = md["scope"]
                                    del md["scope"]
                                for k, v in md.items():
                                    metadata[k] = safe_parse_if_looks_like_json(v)
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Error parsing x-agentuity-metadata: {value}"
                                )
                        else:
                            metadata[key[12:]] = safe_parse_if_looks_like_json(value)

                span.set_attribute("@agentuity/scope", scope)

                # Devmode: make sure to data in metadata since its not coming through catalyst
                if metadata is None:
                    metadata = {}
                if "headers" not in metadata:
                    metadata["headers"] = {}
                    for k, v in request.headers.items():
                        metadata["headers"][k] = v
                if "method" not in metadata:
                    metadata["method"] = request.method
                if "url" not in metadata:
                    metadata["url"] = str(request.url)

                agent_request = AgentRequest(
                    trigger, metadata, contentType, request.content
                )
                agent_context = AgentContext(
                    base_url=base_url,
                    api_key=api_key,
                    services={
                        "kv": KeyValueStore(
                            base_url=base_url,
                            api_key=api_key,
                            tracer=tracer,
                        ),
                        "vector": VectorStore(
                            base_url=base_url,
                            api_key=api_key,
                            tracer=tracer,
                        ),
                        "objectstore": ObjectStore(
                            base_url=base_url,
                            api_key=api_key,
                            tracer=tracer,
                        ),
                    },
                    logger=logger,
                    tracer=tracer,
                    agent=agent,
                    agents_by_id=agents_by_id,
                    port=port,
                    run_id=run_id,
                    scope=scope,
                )
                agent_response = AgentResponse(
                    context=agent_context,
                    data=agent_request.data,
                )

                # Call the run function and get the response
                response = await run_agent(
                    tracer, agentId, agent, agent_request, agent_response, agent_context
                )

                if response is None:
                    return web.Response(
                        text="No response from agent",
                        status=204,
                        headers=make_response_headers(request, "text/plain"),
                    )

                if isinstance(response, AgentResponse):
                    # Check if there's a pending handoff and execute it
                    if response.has_pending_handoff:
                        try:
                            response = await response._execute_handoff()
                        except Exception as e:
                            logger.error(f"Handoff execution failed: {e}")
                            headers = make_response_headers(request, "text/plain")
                            return web.Response(
                                text=f"Handoff failed: {str(e)}",
                                status=500,
                                headers=headers,
                            )

                    return await stream_response(
                        request, response, response.content_type, response.metadata
                    )

                if isinstance(response, web.Response):
                    return response

                if isinstance(response, Data):
                    headers = make_response_headers(request, response.content_type)
                    stream = await response.stream()
                    return await stream_response(request, stream, response.content_type)

                if isinstance(response, dict) or isinstance(response, list):
                    headers = make_response_headers(request, "application/json")
                    return web.Response(body=json.dumps(response), headers=headers)

                if isinstance(response, (str, int, float, bool)):
                    headers = make_response_headers(request, "text/plain")
                    return web.Response(text=str(response), headers=headers)

                if isinstance(response, bytes):
                    headers = make_response_headers(request, "application/octet-stream")
                    return web.Response(
                        body=response,
                        headers=headers,
                    )

                raise ValueError(f"Unsupported response type: {type(response)}")

            except Exception as e:
                print(traceback.format_exc())
                logger.error(f"Error loading or running agent: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                # Handle specific error types more gracefully
                error_msg = str(e)
                if (
                    "closing transport" in error_msg.lower()
                    or "connection reset" in error_msg.lower()
                ):
                    # Client disconnected, don't try to send a response
                    logger.warning(
                        f"Client disconnected during request processing: {error_msg}"
                    )
                    return web.Response(status=499)  # Client Closed Request
                elif "timeout" in error_msg.lower():
                    headers = make_response_headers(request, "text/plain")
                    return web.Response(
                        text="Request timed out",
                        status=504,  # Gateway Timeout
                        headers=headers,
                    )
                else:
                    headers = make_response_headers(request, "text/plain")
                    body = str(e)
                    if (
                        os.getenv("AGENTUITY_ENVIRONMENT", "development")
                        == "development"
                    ):
                        body += "\n\n" + traceback.format_exc()
                    return web.Response(
                        text=body,
                        status=500,
                        headers=headers,
                    )
    else:
        message = f"Agent {agentId} not found" if "agent_" in agentId else "Not found"
        # Agent not found
        return web.Response(
            text=message,
            status=404,
            headers=make_response_headers(request, "text/plain"),
        )


async def handle_health_check(request):
    return web.Response(
        text="OK",
        headers=make_response_headers(
            request,
            "text/plain",
            None,
            dict({"x-agentuity-version": __version__}),
        ),
    )


async def handle_index(request):
    buf = "The following Agent routes are available:\n\n"
    agents_by_id = request.app["agents_by_id"]
    id = "agent_1234"
    for agent in agents_by_id.values():
        id = agent["id"]
        buf += f"POST /{agent['id']} - [{agent['name']}]\n"
    buf += "\n"
    if platform.system() != "Windows":
        buf += "Example usage:\n\n"
        buf += f'curl http://localhost:{port}/{id} \\\n\t--json \'{{"message":"Hello, world!"}}\'\n'
        buf += "\n"
    return web.Response(text=buf, content_type="text/plain")


def get_agent_filepath(agent_name: str) -> str:
    """
    Get the filepath for an agent, checking both new and legacy directory structures.
    First tries the new 'agentuity-agents' directory, then falls back to the legacy 'agents' directory.
    """
    safe_name = safe_python_name(agent_name)

    # Try new structure first
    new_path = os.path.join(os.getcwd(), "agentuity-agents", safe_name, "agent.py")
    if os.path.exists(new_path):
        return new_path

    # Fall back to legacy structure for backwards compatibility
    legacy_path = os.path.join(os.getcwd(), "agents", safe_name, "agent.py")
    if os.path.exists(legacy_path):
        logger.warning(
            f"Using legacy agents directory structure for {agent_name}. Consider migrating to 'agentuity-agents' directory."
        )
        return legacy_path

    # Return new path as default (for error reporting)
    return new_path


def load_config() -> Tuple[Optional[dict], str]:
    # Load agents from config file
    config_data = None
    config_path = os.path.join(os.getcwd(), ".agentuity", "config.json")
    if os.path.exists(config_path):
        logger.info(f"Loading config from {config_path}")
        with open(config_path, "r") as config_file:
            config_data = json.load(config_file)
            for agent in config_data["agents"]:
                agent["filename"] = get_agent_filepath(agent["name"])
    else:
        config_path = os.path.join(os.getcwd(), "agentuity.yaml")
        if os.path.exists(config_path):
            logger.debug(f"Loading config from {config_path}")
            with open(config_path, "r") as config_file:
                from yaml import safe_load

                agent_config = safe_load(config_file)
                config_data = {"agents": []}
                config_data["environment"] = "development"
                config_data["cli_version"] = "unknown"
                config_data["app"] = {"name": agent_config["name"], "version": "dev"}
                for agent in agent_config["agents"]:
                    config = {}
                    config["id"] = agent["id"]
                    config["name"] = agent["name"]
                    config["filename"] = get_agent_filepath(agent["name"])
                    config_data["agents"].append(config)
        else:
            raise Exception(f"No config file found at {config_path}")
    return config_data, config_path


def load_agents(config_data):
    try:
        agents_by_id = {}
        for agent in config_data["agents"]:
            if not os.path.exists(agent["filename"]):
                logger.error(f"Agent {agent['name']} not found at {agent['filename']}")
                sys.exit(1)
            logger.debug(f"Loading agent {agent['name']} from {agent['filename']}")
            agent_module = load_agent_module(
                agent_id=agent["id"],
                name=agent["name"],
                filename=agent["filename"],
            )
            agents_by_id[agent["id"]] = {
                "id": agent["id"],
                "name": agent["name"],
                "filename": agent["filename"],
                "run": agent_module["run"],
                "welcome": (
                    agent_module["welcome"]
                    if "welcome" in agent_module and agent_module["welcome"] is not None
                    else None
                ),
            }
        logger.info(f"Loaded {len(agents_by_id)} agents")
        for agent in agents_by_id.values():
            logger.info(f"Loaded agent: {agent['name']} [{agent['id']}]")
        return agents_by_id
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing agent configuration: {e}")
        sys.exit(1)
    except Exception as e:
        traceback.print_exc()
        logger.error(f"Error loading agent configuration: {e}")
        sys.exit(1)


def autostart(callback: Callable[[], None] = None):
    # Create an event loop and run the async initialization
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    logger.setLevel(logging.INFO)
    config_data, config_file = load_config()

    if config_data is None:
        logger.error(f"No required config file found: {config_file}")
        sys.exit(1)

    loghandler = init(
        {
            "cliVersion": config_data["cli_version"],
            "environment": config_data["environment"],
            "app_name": config_data["app"]["name"],
            "app_version": config_data["app"]["version"],
        },
    )

    instrument()

    callback() if callback else None

    agents_by_id = load_agents(config_data)

    if len(agents_by_id) == 0:
        logger.error(f"No agents found in config file: {config_file}")
        sys.exit(1)

    if loghandler:
        logger.addHandler(loghandler)

    # Create the web application
    app = web.Application()

    # Store agents_by_id in the app state
    app["agents_by_id"] = agents_by_id

    # Add routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/_health", handle_health_check)
    for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
        app.router.add_route(method, "/{agent_id}{tail:.*}", handle_agent_request)
    app.router.add_options("/{agent_id}{tail:.*}", handle_agent_options_request)
    app.router.add_get("/welcome", handle_welcome_request)
    app.router.add_get("/welcome/{agent_id}", handle_agent_welcome_request)

    # Start the server
    logger.info(f"Starting server on port {port}")

    host = (
        "127.0.0.1"
        if os.environ.get("AGENTUITY_ENVIRONMENT") == "development"
        else "0.0.0.0"
    )

    # Run the application
    web.run_app(app, host=host, port=port, access_log=None)
