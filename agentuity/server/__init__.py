import importlib.util
import json
import logging
import os
import signal
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

from opentelemetry import trace
from opentelemetry.propagate import extract, inject

from agentuity.otel import init
from agentuity.instrument import instrument

from .types import AgentContext, AgentRequest, AgentResponse

logger = logging.getLogger(__name__)


# Utility function to inject trace context into response headers
def inject_trace_context(handler):
    """Inject trace context into response headers using configured propagators."""
    try:
        response_headers = {}
        inject(response_headers)

        # Add headers from the propagator to the response
        for header_name, header_value in response_headers.items():
            handler.send_header(header_name, header_value)
    except Exception as e:
        # Log the error but don't fail the request
        logger.error(f"Error injecting trace context: {e}")


def autostart():
    loghandler = None
    instrument()

    def load_agent_module(agent_id, filename):
        agent_path = os.path.join(os.getcwd(), filename)

        # Load the agent module dynamically
        spec = importlib.util.spec_from_file_location(agent_id, agent_path)
        if spec is None:
            raise ImportError(f"Could not load module for {filename}")

        agent_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(agent_module)

        # Check if the module has a run function
        if hasattr(agent_module, "run") and callable(agent_module.run):
            return agent_module.run
        else:
            raise ImportError(f"Module {filename} does not have a run function")

    # Load agents from config file
    try:
        config_path = os.path.join(os.getcwd(), ".agentuity", "config.json")
        config_data = {}
        agents_by_id = {}
        if os.path.exists(config_path):
            with open(config_path, "r") as config_file:
                config_data = json.load(config_file)
                agents = config_data.get("agents", [])
                agents_by_id = {
                    agent["id"]: {
                        "run": load_agent_module(agent["id"], agent["filename"]),
                        "name": agent["name"],
                    }
                    for agent in agents
                }
        else:
            config_path = os.path.join(os.getcwd(), "agentuity.yaml")
            print(f"Loading dev agent configuration from {config_path}")
            if os.path.exists(config_path):
                from yaml import safe_load

                with open(config_path, "r") as f:
                    agentconfig = safe_load(f)
                    config_data["environment"] = "development"
                    config_data["cli_version"] = "unknown"
                    config_data["app"] = {"name": agentconfig["name"], "version": "dev"}
                    for agent in agentconfig["agents"]:
                        filename = os.path.join(
                            os.getcwd(), "agents", agent["name"], "agent.py"
                        )
                        agents_by_id[agent["id"]] = {
                            "id": agent["id"],
                            "name": agent["name"],
                            "filename": filename,
                            "run": load_agent_module(agent["id"], filename),
                        }
            else:
                print(f"No agent configuration found at {config_path}")
                sys.exit(1)
        print(f"Loaded {len(agents_by_id)} agents from {config_path}")

        # if "services" not in config_data:
        #     config_data["services"] = {"kv": KeyValueAPI(), "vector": VectorAPI()}

        loghandler = init(
            {
                "cliVersion": config_data["cli_version"],
                "environment": config_data["environment"],
                "app_name": config_data["app"]["name"],
                "app_version": config_data["app"]["version"],
            }
        )
    except json.JSONDecodeError as e:
        print(f"Error parsing agent configuration: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error loading agent configuration: {e}")
        sys.exit(1)

    logger.setLevel(logging.DEBUG)
    if loghandler:
        logger.addHandler(loghandler)

    for agentId, agent in agents_by_id.items():
        logger.info(f"registered {agent['name']} at /{agentId}")

    class WebRequestHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            # Override to suppress log messages
            return

        def do_GET(self):
            # Check if the path is a health check
            print(f"Processing GET request: {self.path}")
            if self.path == "/_health":
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write("OK".encode("utf-8"))
            else:
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write("Not Found".encode("utf-8"))

        def run_agent(self, tracer, agentId, agent, payload):
            with tracer.start_as_current_span("agent.run") as span:
                span.set_attribute("@agentuity/agentId", agentId)
                span.set_attribute("@agentuity/agentName", agent["name"])
                try:
                    agent_request = AgentRequest(payload or {})
                    agent_request.validate()

                    agent_response = AgentResponse()
                    agent_context = AgentContext(
                        services={},  # need to sync on how best to get these in
                        logger=logger,
                        tracer=tracer,
                        request=agent_request,
                    )

                    result = agent["run"](
                        request=agent_request,
                        response=agent_response,
                        context=agent_context,
                    )

                    ## TODO: in JS sdk you can just return a string, number, boolean, or object
                    ## and it will be converted to the correct type

                    if not isinstance(result, AgentResponse):
                        raise ValueError("Agent must return AgentResponse instance")

                    return result

                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    logger.error(f"Agent execution failed: {str(e)}")
                    raise e

        def do_POST(self):
            # Extract the agent ID from the path (remove leading slash)
            agentId = self.path[1:]
            print(f"Processing request for agent: {agentId}")

            logger.debug(f"request: POST /{agentId}")

            # Read and parse the request body as JSON
            payload = None
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length > 0:
                body = self.rfile.read(content_length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    self.send_response(400)
                    self.send_header("Content-Type", "text/plain")
                    self.end_headers()
                    self.wfile.write("Invalid JSON in request body".encode("utf-8"))
                    return
            else:
                self.send_response(400)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write("No Content-Length header provided".encode("utf-8"))
                return

            # Check if the agent exists in our map
            if agentId in agents_by_id:
                agent = agents_by_id[agentId]
                tracer = trace.get_tracer("http-server")

                # Extract trace context from headers
                context = extract(carrier=dict(self.headers))

                # TODO: review these to match JS
                with tracer.start_as_current_span(
                    "POST /" + agentId,
                    context=context,
                    kind=trace.SpanKind.SERVER,
                    attributes={
                        "http.method": "POST",
                        "http.url": f"http://{self.headers.get('Host', '')}{self.path}",
                        "http.host": self.headers.get("Host", ""),
                        "http.user_agent": self.headers.get("user-agent"),
                        "http.path": self.path,
                    },
                ) as span:
                    try:
                        # Call the run function and get the response
                        response = self.run_agent(tracer, agentId, agent, payload)

                        # Send successful response
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")

                        # Use propagator to inject trace context into response headers
                        inject_trace_context(self)

                        self.end_headers()

                        content_type = response.content_type
                        metadata = response.metadata or {}
                        payload = response.payload

                        self.wfile.write(
                            json.dumps(
                                {
                                    "contentType": content_type,
                                    "payload": payload,
                                    "metadata": metadata,
                                }
                            ).encode("utf-8")
                        )
                        span.set_status(trace.Status(trace.StatusCode.OK))
                    except Exception as e:
                        print(f"Error loading or running agent: {e}")
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        # Send error response
                        self.send_response(500)
                        self.send_header("Content-Type", "text/plain")
                        # Use propagator to inject trace context into response headers
                        inject_trace_context(self)
                        self.end_headers()
                        self.wfile.write(
                            str(f"Error loading or running agent: {str(e)}").encode(
                                "utf-8"
                            )
                        )
            else:
                # Agent not found
                self.send_response(404)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(f"Agent {agentId} not found".encode("utf-8"))

    def signal_handler(sig, frame):
        print("\nShutting down the server...")
        sys.exit(0)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 3500))

    logger.info(f"Python server started on port {port}")
    server = HTTPServer(("0.0.0.0", port), WebRequestHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down the server...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        server.server_close()
