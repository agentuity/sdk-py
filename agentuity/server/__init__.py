import importlib.util
import json
import logging
import os
import sys
import asyncio
import aiohttp
import platform
from aiohttp import web
from aiohttp_sse import sse_response
import base64

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

logger = logging.getLogger(__name__)
port = int(os.environ.get("PORT", 3500))


# Utility function to inject trace context into response headers
def inject_trace_context(headers):
    """Inject trace context into response headers using configured propagators."""
    try:
        inject(headers)
    except Exception as e:
        # Log the error but don't fail the request
        logger.error(f"Error injecting trace context: {e}")


async def load_agent_module(agent_id: str, name: str, filename: str):
    agent_path = os.path.join(os.getcwd(), filename)

    # Load the agent module dynamically
    spec = importlib.util.spec_from_file_location(agent_id, agent_path)
    if spec is None:
        raise ImportError(f"Could not load module for {filename}")

    agent_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(agent_module)

    # Check if the module has a run function
    if not hasattr(agent_module, "run"):
        raise AttributeError(f"Module {filename} does not have a run function")

    logger.debug(f"Loaded agent: {agent_id}")

    return {
        "id": agent_id,
        "name": name,
        "run": agent_module.run,
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
                        base_url=os.environ.get("AGENTUITY_URL"),
                        api_key=os.environ.get("AGENTUITY_API_KEY"),
                        tracer=tracer,
                    ),
                    "vector": VectorStore(
                        base_url=os.environ.get("AGENTUITY_URL"),
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


async def load_agents():
    # Load agents from config file
    try:
        config_path = os.path.join(os.getcwd(), ".agentuity", "config.json")
        config_data = {}
        agents_by_id = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)
                agents = config_data.get("agents", [])
                agents_by_id = {}
                for agent in agents:
                    agent_module = await load_agent_module(
                        agent["id"], agent["name"], agent["filename"]
                    )
                    agents_by_id[agent["id"]] = {
                        "run": agent_module["run"],
                        "name": agent["name"],
                        "id": agent["id"],
                    }
        else:
            config_path = os.path.join(os.getcwd(), "agentuity.yaml")
            logger.info(f"Loading dev agent configuration from {config_path}")
            if os.path.exists(config_path):
                from yaml import safe_load

                with open(config_path, "r") as f:
                    agentconfig = safe_load(f)
                    config_data["environment"] = "development"
                    config_data["cli_version"] = "unknown"
                    config_data["app"] = {"name": agentconfig["name"], "version": "dev"}
                    agents_by_id = {}
                    for agent in agentconfig["agents"]:
                        filename = os.path.join(
                            os.getcwd(), "agents", agent["name"], "agent.py"
                        )
                        agent_module = await load_agent_module(
                            agent["id"], agent["name"], filename
                        )
                        agents_by_id[agent["id"]] = {
                            "id": agent["id"],
                            "name": agent["name"],
                            "filename": filename,
                            "run": agent_module["run"],
                        }
        logger.info(f"Loaded {len(agents_by_id)} agents from {config_path}")
        for agent in agents_by_id.values():
            logger.info(f"Loaded agent: {agent['name']} [{agent['id']}]")
        return init(
            {
                "cliVersion": config_data["cli_version"],
                "environment": config_data["environment"],
                "app_name": config_data["app"]["name"],
                "app_version": config_data["app"]["version"],
            }
        ), agents_by_id
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing agent configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error loading agent configuration: {e}")
        sys.exit(1)


def autostart():
    instrument()

    # Create an event loop and run the async initialization
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    logger.setLevel(logging.INFO)

    # Run load_agents in the event loop
    loghandler, agents_by_id = loop.run_until_complete(load_agents())

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

    # Start the server
    logger.info(f"Starting server on port {port}")

    # Run the application
    web.run_app(app, host="0.0.0.0", port=port, access_log=None)
