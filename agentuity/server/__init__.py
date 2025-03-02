import os
import json
import signal
import sys
import base64
import importlib.util
import logging
from http.server import HTTPServer
from http.server import BaseHTTPRequestHandler
from agentuity.otel import init


def autostart():
    loghandler = None

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

    from opentelemetry import trace

    logger = logging.getLogger("agentuity")
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

        def run_agent(self, tracer, agentId, agent):
            # TODO: add the logic for running the agent here
            with tracer.start_as_current_span("agent.run") as span:
                span.set_attribute("agentId", agentId)
                span.set_attribute("agentName", agent["name"])
                try:
                    response = agent["run"]()
                    span.set_status(trace.Status(trace.StatusCode.OK))
                    return response
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                    raise e

        def do_POST(self):
            # Extract the agent ID from the path (remove leading slash)
            agentId = self.path[1:]
            print(f"Processing request for agent: {agentId}")

            logger.debug(f"request: POST /{agentId}")

            # Check if the agent exists in our map
            if agentId in agents_by_id:
                agent = agents_by_id[agentId]
                tracer = trace.get_tracer("http-server")

                with tracer.start_as_current_span(
                    "POST /" + agentId,
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
                        response = self.run_agent(tracer, agentId, agent)

                        # Send successful response
                        self.send_response(200)
                        self.send_header("Content-Type", "application/json")
                        self.end_headers()

                        content_type = "text/plain"
                        # Base64 encode the payload
                        encoded_payload = base64.b64encode(
                            str(response).encode("utf-8")
                        ).decode("utf-8")

                        self.wfile.write(
                            json.dumps(
                                {
                                    "contentType": content_type,
                                    "payload": encoded_payload,
                                    "metadata": {},
                                }
                            ).encode("utf-8")
                        )
                        span.set_status(trace.Status(trace.StatusCode.OK))
                    except Exception as e:
                        print(f"Error loading or running agent: {e}")
                        span.record_exception(e)
                        span.set_status(trace.Status(trace.StatusCode.ERROR, str(e)))
                        self.send_response(500)
                        self.send_header("Content-Type", "text/plain")
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

    def signal_handler(sig, frame):
        print("\nShutting down the server...")
        sys.exit(0)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Get port from environment variable or use default
    port = int(os.environ.get("PORT", 3500))

    logger.info(f"Python server started on port {port}")
    server = HTTPServer(("127.0.0.1", port), WebRequestHandler)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down the server...")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        server.server_close()
