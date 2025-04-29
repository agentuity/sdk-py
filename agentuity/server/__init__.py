import importlib.util
import json
import logging
import os
import sys
import asyncio
import aiohttp
import platform
import re
from aiohttp import web
from aiohttp_sse import sse_response
import base64
from typing import Callable, Any
import traceback

from opentelemetry import trace
from opentelemetry.propagate import extract, inject

from agentuity.otel import init
from agentuity.instrument import instrument

from .data import Data, encode_payload
from .context import AgentContext
from .request import AgentRequest
from .response import AgentResponse
from .keyvalue import KeyValueStore
from .vector import VectorStore
from .agent import RemoteAgentResponse
from .data import value_to_payload

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


async def run_agent(tracer, agentId, agent, payload, agents_by_id):
    with tracer.start_as_current_span("agent.run") as span:
        span.set_attribute("@agentuity/agentId", agentId)
        span.set_attribute("@agentuity/agentName", agent["name"])
        try:
            agent_request = AgentRequest(payload)
            agent_request.validate()

            agent_response = AgentResponse(
                payload=payload, tracer=tracer, agents_by_id=agents_by_id, port=port
            )
            agent_context = AgentContext(
                services={
                    "kv": KeyValueStore(
                        base_url=os.environ.get(
                            "AGENTUITY_TRANSPORT_URL", "https://agentuity.ai"
                        ),
                        api_key=os.environ.get("AGENTUITY_API_KEY"),
                        tracer=tracer,
                    ),
                    "vector": VectorStore(
                        base_url=os.environ.get(
                            "AGENTUITY_TRANSPORT_URL", "https://agentuity.ai"
                        ),
                        api_key=os.environ.get("AGENTUITY_API_KEY"),
                        tracer=tracer,
                    ),
                },
                logger=logger,
                tracer=tracer,
                agent=agent,
                agents_by_id=agents_by_id,
                port=port,
            )

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


async def handle_run_request(request):
    agentId = request.match_info["agent_id"]
    logger.debug(f"request: POST /run/{agentId}")

    body = await request.read()

    payload = {
        "trigger": "manual",
        "contentType": request.headers.get("Content-Type", "application/json"),
        "payload": base64.b64encode(body).decode("utf-8"),
        "metadata": {
            "headers": dict(request.headers),
        },
    }

    async with aiohttp.ClientSession() as session:
        target_url = f"http://127.0.0.1:{port}/{agentId}"

        try:
            # Make the request and get the response
            async with session.post(
                target_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300,  # Add a timeout to prevent hanging
            ) as response:
                # Read the entire response body
                response_body = await response.read()

                # Try to parse as JSON
                try:
                    # Parse the response as JSON
                    response_json = json.loads(response_body)

                    content_type = response_json["contentType"]
                    body = base64.b64decode(response_json["payload"])

                    resp = web.Response(
                        status=response.status,
                        body=body,
                        content_type=content_type,
                    )

                    # Copy relevant headers from the original response
                    for header_name, header_value in response.headers.items():
                        if header_name.lower() not in (
                            "content-length",
                            "content-type",
                        ):
                            resp.headers[header_name] = header_value

                    # Add trace context to response headers
                    inject_trace_context(resp.headers)

                    return resp

                except json.JSONDecodeError:
                    # If not JSON, fall back to streaming the original response
                    resp = web.StreamResponse(
                        status=response.status,
                        reason=response.reason,
                        headers=response.headers,
                    )

                    # Add trace context to response headers
                    inject_trace_context(resp.headers)

                    # Start the response
                    await resp.prepare(request)

                    # Write the original body
                    await resp.write(response_body)
                    await resp.write_eof()

                    return resp

        except aiohttp.ClientError as e:
            # Handle HTTP errors
            logger.error(f"HTTP error occurred: {str(e)}")
            resp = web.json_response(
                {
                    "error": "Bad Gateway",
                    "message": f"Error forwarding request to {target_url}",
                    "details": str(e),
                },
                status=502,
            )
            # Only add trace context, not Content-Type
            inject_trace_context(resp.headers)
            return resp

        except Exception as e:
            resp = web.json_response(
                {
                    "error": "Internal Server Error",
                    "message": "An unexpected error occurred",
                    "details": str(e),
                },
                status=500,
            )
            inject_trace_context(resp.headers)
            logger.error(f"Error in handle_sdk_request: {str(e)}")
            return resp


def isBase64Content(val: Any) -> bool:
    if isinstance(val, str):
        return (
            re.match(
                r"^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$", val
            )
            is not None
        )
    return False


def encode_welcome(val):
    if isinstance(val, dict):
        if "prompts" in val:
            for prompt in val["prompts"]:
                if "data" in prompt:
                    if not isBase64Content(prompt["data"]):
                        payload = value_to_payload(
                            prompt.get("contentType", "text/plain"), prompt["data"]
                        )
                        ct = payload["contentType"]
                        if (
                            "text/" in ct
                            or "json" in ct
                            or "image" in ct
                            or "audio" in ct
                            or "video" in ct
                        ):
                            prompt["data"] = encode_payload(payload["payload"])
                        else:
                            prompt["data"] = payload["payload"]
                        prompt["contentType"] = ct
        else:
            for key, value in val.items():
                val[key] = encode_welcome(value)
    return val


async def handle_welcome_request(request: web.Request):
    res = {}
    for agent in request.app["agents_by_id"].values():
        if "welcome" in agent and agent["welcome"] is not None:
            fn = agent["welcome"]()
            if isinstance(fn, dict):
                res[agent["id"]] = encode_welcome(fn)
            else:
                res[agent["id"]] = encode_welcome(await fn)
    return web.json_response(res)


async def handle_agent_welcome_request(request: web.Request):
    agents_by_id = request.app["agents_by_id"]
    if request.match_info["agent_id"] in agents_by_id:
        agent = agents_by_id[request.match_info["agent_id"]]
        if "welcome" in agent and agent["welcome"] is not None:
            fn = agent["welcome"]()
            if not isinstance(fn, dict):
                fn = encode_welcome(await fn)
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


async def handle_agent_request(request: web.Request):
    # Access the agents_by_id from the app state
    agents_by_id = request.app["agents_by_id"]

    agentId = request.match_info["agent_id"]
    logger.debug(f"request: POST /{agentId}")

    # Read and parse the request body as JSON
    try:
        payload = await request.json()
    except json.JSONDecodeError:
        return web.Response(
            text="Invalid JSON in request body", status=400, content_type="text/plain"
        )

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
                is_sse = request.headers.get("accept") == "text/event-stream"

                # Call the run function and get the response
                response = run_agent(tracer, agentId, agent, payload, agents_by_id)

                # Prepare response headers
                headers = {}  # Don't include Content-Type in headers
                inject_trace_context(headers)

                # handle server side events
                if is_sse:
                    async with sse_response(request, headers=headers) as resp:
                        response = await response
                        if not isinstance(response, AgentResponse):
                            return web.Response(
                                text="Expected a AgentResponse response when using SSE",
                                status=500,
                                headers=headers,
                                content_type="text/plain",
                            )
                        if not response.is_stream:
                            return web.Response(
                                text="Expected a stream response when using SSE",
                                status=500,
                                headers=headers,
                                content_type="text/plain",
                            )
                        for chunk in response:
                            if chunk is None:
                                resp.force_close()
                                break
                            await resp.send(chunk)
                    return resp

                # handle normal response
                response = await response

                if isinstance(response, AgentResponse):
                    payload = response.payload
                    if response.is_stream:
                        payload = ""
                        for chunk in response:
                            if chunk is not None:
                                payload += chunk
                        payload = encode_payload(payload)
                    response = {
                        "contentType": response.content_type,
                        "payload": payload,
                        "metadata": response.metadata,
                    }
                elif isinstance(response, RemoteAgentResponse):
                    response = {
                        "contentType": response.contentType,
                        "payload": response.data.base64,
                        "metadata": response.metadata,
                    }
                elif isinstance(response, Data):
                    response = {
                        "contentType": response.contentType,
                        "payload": response.base64,
                        "metadata": {},
                    }
                elif isinstance(response, dict) or isinstance(response, list):
                    response = {
                        "contentType": "application/json",
                        "payload": encode_payload(json.dumps(response)),
                        "metadata": {},
                    }
                elif isinstance(response, (str, int, float, bool)):
                    response = {
                        "contentType": "text/plain",
                        "payload": encode_payload(str(response)),
                        "metadata": {},
                    }
                elif isinstance(response, bytes):
                    response = {
                        "contentType": "application/octet-stream",
                        "payload": base64.b64encode(response).decode("utf-8"),
                        "metadata": {},
                    }
                else:
                    raise ValueError("Unsupported response type")

                span.set_status(trace.Status(trace.StatusCode.OK))
                return web.json_response(response, headers=headers)

            except Exception as e:
                logger.error(f"Error loading or running agent: {e}")
                span.record_exception(e)
                span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))

                # Prepare error response
                headers = {}  # Don't include Content-Type in headers
                inject_trace_context(headers)

                return web.Response(
                    text=str(e),
                    status=500,
                    headers=headers,
                    content_type="text/plain",  # Set content_type separately
                )
    else:
        # Agent not found
        return web.Response(
            text=f"Agent {agentId} not found", status=404, content_type="text/plain"
        )


async def handle_health_check(request):
    return web.json_response({"status": "ok"})


async def handle_index(request):
    buf = "The following Agent routes are available:\n\n"
    agents_by_id = request.app["agents_by_id"]
    id = "agent_1234"
    for agent in agents_by_id.values():
        id = agent["id"]
        buf += f"POST /run/{agent['id']} - [{agent['name']}]\n"
    buf += "\n"
    if platform.system() != "Windows":
        buf += "Example usage:\n\n"
        buf += f'curl http://localhost:{port}/run/{id} \\\n\t--json \'{{"message":"Hello, world!"}}\'\n'
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
    app.router.add_post("/run/{agent_id}", handle_run_request)
    app.router.add_post("/{agent_id}", handle_agent_request)
    app.router.add_get("/welcome", handle_welcome_request)
    app.router.add_get("/welcome/{agent_id}", handle_agent_welcome_request)

    # Start the server
    logger.info(f"Starting server on port {port}")

    # Run the application
    web.run_app(app, host="127.0.0.1", port=port, access_log=None)
