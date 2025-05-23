import importlib.util
import json
import logging
import os
import sys
import asyncio
import platform
import re
from aiohttp import web
from typing import Callable, Iterable, Any
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
from .data import dataLikeToData

logger = logging.getLogger(__name__)
port = int(os.environ.get("AGENTUITY_CLOUD_PORT", os.environ.get("PORT", 3500)))


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
                        ct = data.contentType
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
    if request.headers.get("origin"):
        headers["Access-Control-Allow-Origin"] = request.headers.get("origin")
    else:
        headers["Access-Control-Allow-Origin"] = "*"
    headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
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
    await resp.prepare(request)

    if hasattr(iterable, "__anext__"):
        # Handle async iterators
        async for chunk in iterable:
            if chunk is not None:
                await resp.write(chunk)
    else:
        # Handle regular iterators
        for chunk in iterable:
            if chunk is not None:
                await resp.write(chunk)

    await resp.write_eof()
    return resp


async def handle_agent_options_request(request: web.Request):
    return web.Response(
        headers=make_response_headers(request, "text/plain"),
        text="OK",
    )


async def handle_agent_request(request: web.Request):
    # Access the agents_by_id from the app state
    agents_by_id = request.app["agents_by_id"]

    agentId = request.match_info["agent_id"]
    logger.debug(f"request: POST /{agentId}")

    # Check if the agent exists in our map
    if agentId in agents_by_id:
        agent = agents_by_id[agentId]
        tracer = trace.get_tracer("http-server")

        # Extract trace context from headers
        context = extract(carrier=dict(request.headers))

        with tracer.start_as_current_span(
            "HTTP POST",
            context=context,
            kind=trace.SpanKind.SERVER,
            attributes={
                "http.method": "POST",
                "http.url": str(request.url),
                "http.host": request.host,
                "http.user_agent": request.headers.get("user-agent"),
                "http.path": request.path,
                "@agentuity/agentId": agentId,
                "@agentuity/agentName": agent["name"],
            },
        ) as span:
            try:
                trigger = request.headers.get("x-agentuity-trigger", "manual")
                contentType = request.headers.get(
                    "content-type", "application/octet-stream"
                )
                metadata = {}
                scope = "local"
                if span.is_recording():
                    run_id = span.get_span_context().trace_id
                else:
                    run_id = None
                for key, value in request.headers.items():
                    if key.startswith("x-agentuity-") and key != "x-agentuity-trigger":
                        if key == "x-agentuity-run-id":
                            run_id = value
                        elif key == "x-agentuity-scope":
                            scope = value
                        elif key == "x-agentuity-metadata":
                            try:
                                metadata = json.loads(value)
                                if "runid" in metadata:
                                    run_id = metadata["runid"]
                                    del metadata["runid"]
                                if "scope" in metadata:
                                    scope = metadata["scope"]
                                    del metadata["scope"]
                            except json.JSONDecodeError:
                                logger.error(
                                    f"Error parsing x-agentuity-metadata: {value}"
                                )
                        else:
                            metadata[key[12:]] = value

                span.set_attribute("@agentuity/scope", scope)

                agent_request = AgentRequest(
                    trigger, metadata, contentType, request.content
                )
                agent_context = AgentContext(
                    base_url=os.environ.get(
                        "AGENTUITY_TRANSPORT_URL", "https://agentuity.ai"
                    ),
                    api_key=os.environ.get("AGENTUITY_API_KEY")
                    or os.environ.get("AGENTUITY_SDK_KEY"),
                    services={
                        "kv": KeyValueStore(
                            base_url=os.environ.get(
                                "AGENTUITY_TRANSPORT_URL", "https://agentuity.ai"
                            ),
                            api_key=os.environ.get("AGENTUITY_API_KEY")
                            or os.environ.get("AGENTUITY_SDK_KEY"),
                            tracer=tracer,
                        ),
                        "vector": VectorStore(
                            base_url=os.environ.get(
                                "AGENTUITY_TRANSPORT_URL", "https://agentuity.ai"
                            ),
                            api_key=os.environ.get("AGENTUITY_API_KEY")
                            or os.environ.get("AGENTUITY_SDK_KEY"),
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
                    return await stream_response(
                        request, response, response.contentType, response.metadata
                    )

                if isinstance(response, web.Response):
                    return response

                if isinstance(response, Data):
                    headers = make_response_headers(request, response.contentType)
                    return await stream_response(
                        request, response.stream(), response.contentType
                    )

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
                headers = make_response_headers(request, "text/plain")
                return web.Response(
                    text=str(e),
                    status=500,
                    headers=headers,
                )
    else:
        # Agent not found
        return web.Response(
            text=f"Agent {agentId} not found",
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
            dict({"x-agentuity-binary": "true", "x-agentuity-version": __version__}),
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


def load_config() -> Any:
    # Load agents from config file
    config_path = os.path.join(os.getcwd(), ".agentuity", "config.json")
    config_data = None
    if os.path.exists(config_path):
        with open(config_path, "r") as config_file:
            config_data = json.load(config_file)
            for agent in config_data["agents"]:
                config_data["filename"] = os.path.join(
                    os.getcwd(), "agents", agent["name"], "agent.py"
                )
    else:
        config_path = os.path.join(os.getcwd(), "agentuity.yaml")
        if os.path.exists(config_path):
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
                    config["filename"] = os.path.join(
                        os.getcwd(), "agents", agent["name"], "agent.py"
                    )
                    config_data["agents"].append(config)
    return config_data


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
    config_data = load_config()

    if config_data is None:
        logger.error("No agentuityconfig file found")
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

    if loghandler:
        logger.addHandler(loghandler)

    # Create the web application
    app = web.Application()

    # Store agents_by_id in the app state
    app["agents_by_id"] = agents_by_id

    # Add routes
    app.router.add_get("/", handle_index)
    app.router.add_get("/_health", handle_health_check)
    app.router.add_post("/{agent_id}", handle_agent_request)
    app.router.add_options("/{agent_id}", handle_agent_options_request)
    app.router.add_get("/welcome", handle_welcome_request)
    app.router.add_get("/welcome/{agent_id}", handle_agent_welcome_request)

    # Start the server
    logger.info(f"Starting server on port {port}")

    host = (
        "127.0.0.1" if os.environ.get("AGENTUITY_ENV") == "development" else "0.0.0.0"
    )

    # Run the application
    web.run_app(app, host=host, port=port, access_log=None)
