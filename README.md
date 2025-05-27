<div align="center">
    <img src="https://raw.githubusercontent.com/agentuity/sdk-py/main/.github/Agentuity.png" alt="Agentuity" width="100"/> <br/>
    <strong>Build Agents, Not Infrastructure</strong> <br/>
<br />
<a href="https://pypi.org/project/agentuity/"><img alt="Python version" src="https://img.shields.io/pypi/v/agentuity"></a>
<a href="https://github.com/agentuity/sdk-py/blob/main/README.md"><img alt="License" src="https://badgen.now.sh/badge/license/Apache-2.0"></a>
<a href="https://discord.gg/vtn3hgUfuc"><img alt="Join the community on Discord" src="https://img.shields.io/discord/1332974865371758646.svg?style=flat"></a>
</div>
<br />

# Agentuity Python SDK


**Visit [https://agentuity.com](https://agentuity.com) to get started with Agentuity.**



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

```bash
curl -fsSL https://agentuity.sh | sh
```


Once installed, you can create a new project with the following command:

```bash
agentuity new
```


## Development Setup

### Prerequisites

- [Python](https://www.python.org/) (3.10 or 3.11)
- [uv](https://docs.astral.sh/uv/) (latest version recommended)


### Installation

Clone the repository and install dependencies:

```bash
# Clone the repository
git clone https://github.com/agenuity/sdk-py.git
cd sdk-py

# Install dependencies
uv sync
```

### Local Development

Create a new agent project or use an existing one like normal.

To link your local python SDK to your project, run the following commands:

Install the dependencies 
```bash
make install
```

Build the SDK:

```bash
make build
```

In your project, install the local SDK build:

```bash
uv add ~/path/to/sdk-py/dist/agentuity-0.0.83.post2+d07b43907c8002056fe3550ddef946d1dbb0eeff.tar.gz
```

Make sure to replace the path with the actual path to the SDK build.

Now you can run your project like normal.

```bash
agentuity dev
```



## License

See the [LICENSE](LICENSE.md) file for details.
