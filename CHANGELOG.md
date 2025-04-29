# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.79] - 2025-04-29

### Changed
- Bind only to ipv4 loopback address ([#33](https://github.com/agentuity/sdk-py/pull/33))

## [0.0.78] - 2025-04-14

### Added
- Add welcome encoding functionality for agent responses ([#31](https://github.com/agentuity/sdk-py/pull/31))

## [0.0.77] - 2025-04-07

### Added
- Add comprehensive test suite with pytest ([#27](https://github.com/agentuity/sdk-py/pull/27))
- Expand test coverage for logger, context, and langchain instrumentation ([#28](https://github.com/agentuity/sdk-py/pull/28))
- Add agent inspect endpoint support ([#29](https://github.com/agentuity/sdk-py/pull/29))

## [0.0.76] - 2025-04-03

### Fixed
- Fix Langchain instrumentation and add openai-agents dependency ([#24](https://github.com/agentuity/sdk-py/pull/24))

## [0.0.75] - 2025-04-01

### Added
- Add data and markdown methods to AgentResponse class ([#26](https://github.com/agentuity/sdk-py/pull/26))
- Add PyPI release workflow ([#22](https://github.com/agentuity/sdk-py/pull/22))

### Changed
- Update logo URL from relative to absolute path ([#19](https://github.com/agentuity/sdk-py/pull/19))
- Remove 'work in progress' warning from README ([#20](https://github.com/agentuity/sdk-py/pull/20))
- Update Agentuity gateway URL from /llm/ to /gateway/ ([#21](https://github.com/agentuity/sdk-py/pull/21))
- Update to use AGENTUITY_CLOUD_PORT with fallback to PORT ([#23](https://github.com/agentuity/sdk-py/pull/23))
- Use transport instead of API for hosted SDK api ([#25](https://github.com/agentuity/sdk-py/pull/25))
- Update CHANGELOG.md for v0.0.74 ([#18](https://github.com/agentuity/sdk-py/pull/18))

## [0.0.74] - 2025-03-25

### Added
- Better support for OpenAI and Agents framework ([#16](https://github.com/agentuity/sdk-py/pull/16))
- Add agentName to logger ([#17](https://github.com/agentuity/sdk-py/pull/17))

## [0.0.73] - 2025-03-19

### Fixed
- Fix issue with non-stream functionality ([#15](https://github.com/agentuity/sdk-py/pull/15))

## [0.0.72] - 2025-03-16

### Added
- Add the @agentuity/agentId to the context.logger for an agent ([#13](https://github.com/agentuity/sdk-py/pull/13))

### Fixed
- Fix import issue and add ruff for formatting and linting ([#14](https://github.com/agentuity/sdk-py/pull/14))

## [0.0.71] - 2025-03-16

### Added
- SSE and Stream support with new stream() method and improved documentation ([#12](https://github.com/agentuity/sdk-py/pull/12))

## [0.0.70] - 2025-03-13

### Added
- Stream IO Input: add new facility to support stream io for input data ([#10](https://github.com/agentuity/sdk-py/pull/10))

## [0.0.69] - 2025-03-10
