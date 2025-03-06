<div align="center">
    <img src=".github/Agentuity.png" alt="Agentuity" width="100"/> <br/>
    <strong>Build Agents, Not Infrastructure</strong> <br/>
<br />
<a href="https://pypi.org/project/agentuity/"><img alt="Python version" src="https://img.shields.io/pypi/v/agentuity"></a>
<a href="https://github.com/agentuity/sdk-py/blob/main/README.md"><img alt="License" src="https://badgen.now.sh/badge/license/Apache-2.0"></a>
<a href="https://discord.gg/vtn3hgUfuc"><img alt="Join the community on Discord" src="https://img.shields.io/discord/1332974865371758646.svg?style=flat"></a>
</div>
<br />

# Agentuity Python SDK


**Visit [https://agentuity.com](https://agentuity.com) to get started with Agentuity.**

> [!WARNING]  
> This is currently a work in progress and not ready to be opened to the public.



The Agentuity Python SDK is a powerful toolkit for building, deploying, and managing AI agents in Python environments. This SDK provides developers with a comprehensive set of tools to create intelligent, event-driven agents that can process various types of content, communicate with each other, and integrate with external systems.

## Key Features

- **Multi-Agent Architecture**: Build and orchestrate multiple interconnected agents that can communicate and collaborate.
- **Event-Driven Design**: Respond to various triggers including webhooks, cron jobs, SMS, voice, email, and more.
- **Rich Content Handling**: Process and generate multiple content types including JSON, text, markdown, HTML, and binary formats (images, audio, PDFs).
- **Persistent Storage**: Built-in key-value and vector storage capabilities for maintaining state and performing semantic searches.
- **Observability**: Integrated OpenTelemetry support for comprehensive logging, metrics, and tracing.
- **Cross-Runtime Support**: Works seamlessly with both Node.js and Bun runtimes.

## Use Cases

- Building conversational AI systems
- Creating automated workflows with multiple specialized agents
- Developing content processing and generation pipelines
- Implementing intelligent data processing systems
- Building AI-powered APIs and services

## Getting Started

To use this SDK in a real project, you should install the Agentuity CLI.

### Mac OS

```bash
brew tap agentuity/tap && brew install agentuity
```

### Linux or Windows

See the [Agentuity CLI](https://github.com/agenuity/cli) repository for installation instructions and releases.

Once installed, you can create a new project with the following command:

```bash
agentuity new
```


## Development Setup

### Prerequisites

- [Python](https://www.python.org/) (3.11 or higher)
- [uv](https://docs.astral.sh/uv/) (latest version recommended)


### Installation

Clone the repository and install dependencies:

```bash
# Clone the repository
git clone https://github.com/agenuity/sdk-py.git
cd sdk-py

# Install dependencies using uv (recommended)
uv install
```

### Local Development

Create a minimal agentuity.yaml file in the root of the project:

```yaml
project_id: proj_mv0w67c4851eX0oTglYLzP3OgS2BjN54
name: test
agents:
  - id: agent_HaDpiH67c4851eISzbAWfZqwLtnpguW6
    name: myfirstagent
```

Create a test agent:

```bash
mkdir -p agents/myfirstagent
touch agents/myfirstagent/agent.py
```

Create a test agent:

```python
def run(request, response, context):
    return response.text("Hello, world")
```

Run the test server:

```bash
uv run test.py
```

Hit the test endpoint:

```bash
curl -v http://localhost:3500/agent_HaDpiH67c4851eISzbAWfZqwLtnpguW6 --json '{"trigger":"manual","contentType":"text/plain","payload":"aGkK"}'
```

## License

See the [LICENSE](LICENSE.md) file for details.