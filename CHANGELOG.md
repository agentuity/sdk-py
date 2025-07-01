# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.0.100] - 2025-06-30

### Changed
- Shortened Discord interface method name from `discord_message()` to `discord()` for improved usability ([#77](https://github.com/agentuity/sdk-py/pull/77))

### ⚠️ Breaking Changes

The Discord interface method has been renamed from `discord_message()` to `discord()`. Update your code to use the new method name:

```diff
- message = await req.data.discord_message()
+ message = await req.data.discord()
```

## [0.0.99] - 2025-06-30

### Added
- Discord IO support for Python SDK with comprehensive Discord integration capabilities ([#67](https://github.com/agentuity/sdk-py/pull/67))
- New Discord API module for Discord-specific operations and utilities ([#67](https://github.com/agentuity/sdk-py/pull/67))
- Discord data processing support in the data layer for handling Discord-specific content types ([#67](https://github.com/agentuity/sdk-py/pull/67))

## [0.0.98] - 2025-06-19

### Fixed
- Email: text and html should return a str not a list of str to match JS behavior ([#73](https://github.com/agentuity/sdk-py/pull/73))

## [0.0.97] - 2025-06-19

### Fixed
- Filter out empty headers from headers special HTTP header ([#71](https://github.com/agentuity/sdk-py/pull/71))

## [0.0.96] - 2025-06-19

### Added
- Enhanced ObjectStorePutParams with additional headers and metadata support ([#66](https://github.com/agentuity/sdk-py/pull/66))

### Fixed
- Fixed difference in HTTP header casing and other cleanup items ([#69](https://github.com/agentuity/sdk-py/pull/69))

## [0.0.95] - 2025-06-13

### Added
- ObjectStore service with comprehensive object storage capabilities including get, put, delete, and public URL generation ([#65](https://github.com/agentuity/sdk-py/pull/65))

## [0.0.94] - 2025-06-11

### Fixed
- Fixed naming conflict with openAI Agents SDK by renaming agents directory to agentuity-agents with backward compatibility ([#63](https://github.com/agentuity/sdk-py/pull/63))
- Removed ruff from runtime dependencies as it's only needed for development ([#63](https://github.com/agentuity/sdk-py/pull/63))

## [0.0.93] - 2025-06-09

### Fixed
- Improved route handling for extra path segments and better 404 error messages ([#61](https://github.com/agentuity/sdk-py/pull/61))
- Enhanced logging to display actual HTTP method and full request path ([#61](https://github.com/agentuity/sdk-py/pull/61))
- Simplified health check response headers and consolidated route registration ([#61](https://github.com/agentuity/sdk-py/pull/61))

## [0.0.92] - 2025-06-09

### Added
- Email class support for large attachments and send reply functionality ([#59](https://github.com/agentuity/sdk-py/pull/59))
- Structured interfaces for agent requests, context, data, and email processing with streaming and async capabilities ([#59](https://github.com/agentuity/sdk-py/pull/59))
- Ability to send reply emails with attachments and telemetry support ([#59](https://github.com/agentuity/sdk-py/pull/59))

### Changed
- Standardized naming conventions for content type attributes across the application ([#59](https://github.com/agentuity/sdk-py/pull/59))
- Enhanced encapsulation and interface compliance for agent context, data, and request objects ([#59](https://github.com/agentuity/sdk-py/pull/59))
- Deprecated legacy property names in favor of new, consistent ones, with warnings for backward compatibility ([#59](https://github.com/agentuity/sdk-py/pull/59))

### Fixed
- Added OpenTelemetry tracing headers to HTTP requests for improved observability ([#59](https://github.com/agentuity/sdk-py/pull/59))
- Corrected attribute names in tests and code to ensure consistent access to content type properties ([#59](https://github.com/agentuity/sdk-py/pull/59))

## [0.0.91] - 2025-05-31

### Added
- Added LlamaIndex instrumentation for automatic Agentuity gateway integration ([#57](https://github.com/agentuity/sdk-py/pull/57))
- LlamaIndex now automatically uses Agentuity API key and gateway when no OpenAI API key is provided ([#57](https://github.com/agentuity/sdk-py/pull/57))
- OpenAI client patching within LlamaIndex for seamless Agentuity integration ([#57](https://github.com/agentuity/sdk-py/pull/57))

## [0.0.90] - 2025-05-30

### Fixed
- Apply safe filename fix similar to CLI and always prefer to load config but fallback to yaml in dev ([#55](https://github.com/agentuity/sdk-py/pull/55))

## [0.0.89] - 2025-05-29

### Fixed
- Fix outgoing requests missing traceid in OpenTelemetry instrumentation ([#54](https://github.com/agentuity/sdk-py/pull/54))

## [0.0.88] - 2025-05-28

### Added
- Agent startup checks with stack trace printing in development mode ([#52](https://github.com/agentuity/sdk-py/pull/52))

### Fixed
- Fixed issue with OTel trace id not getting propagated correctly and causing it not to be associated with the correct session in production ([#53](https://github.com/agentuity/sdk-py/pull/53))

## [0.0.87] - 2025-05-27

### Fixed
- Fixed handoff issues by implementing deferred handoff execution with improved error handling and agent communication ([#50](https://github.com/agentuity/sdk-py/pull/50))
- Added configurable HTTP timeouts for agent communication ([#50](https://github.com/agentuity/sdk-py/pull/50))
- Improved connection error handling for client disconnections during streaming ([#50](https://github.com/agentuity/sdk-py/pull/50))

## [0.0.86] - 2025-05-24

### Added
- Added Email class for parsing inbound email messages with support for extracting subject, sender, recipients, and attachments ([#48](https://github.com/agentuity/sdk-py/pull/48))
- Added async email() method to Data class for parsing RFC822 email content ([#48](https://github.com/agentuity/sdk-py/pull/48))
- Added mail-parser dependency for email parsing functionality ([#48](https://github.com/agentuity/sdk-py/pull/48))

### Changed
- Updated AgentResponse.handoff() to accept DataLike types instead of only dict for improved flexibility ([#47](https://github.com/agentuity/sdk-py/pull/47))
- Enhanced JSON serialization in AgentResponse.json() with better error handling and fallback for objects with __dict__ ([#48](https://github.com/agentuity/sdk-py/pull/48))

### Fixed
- Fixed duplicate variable assignment in RemoteAgent.run() method ([#47](https://github.com/agentuity/sdk-py/pull/47))

## [0.0.85] - 2025-05-22

### Added
- Added support for constructing data objects from both synchronous and asynchronous byte iterators ([#45](https://github.com/agentuity/sdk-py/pull/45))
- Added synchronous reading methods for data objects ([#45](https://github.com/agentuity/sdk-py/pull/45))

### Changed
- Improved local development instructions in README ([#44](https://github.com/agentuity/sdk-py/pull/44))
- Enhanced agent input handling to accept a broader range of data types ([#45](https://github.com/agentuity/sdk-py/pull/45))
- Configured explicit timeout settings for agent network operations ([#45](https://github.com/agentuity/sdk-py/pull/45))

### Fixed
- Improved data conversion logic to handle a wider range of input types ([#45](https://github.com/agentuity/sdk-py/pull/45))

## [0.0.84] - 2025-05-14

### Added
- Added AGENTUITY_SDK_KEY ([#42](https://github.com/agentuity/sdk-py/pull/42))

## [0.0.83] - 2025-05-09

### Fixed
- Fix issue vectors, better typing for Vector and KeyValue in context ([#40](https://github.com/agentuity/sdk-py/pull/40))

## [0.0.82] - 2025-05-01

### Added
- Async functionality for agent execution and improved agent-to-agent communication ([#38](https://github.com/agentuity/sdk-py/pull/38))

### Changed
- Refactored server module for asynchronous operation support ([#38](https://github.com/agentuity/sdk-py/pull/38))
- Enhanced data handling for better async compatibility ([#38](https://github.com/agentuity/sdk-py/pull/38))

### Fixed
- Various test failures and lint issues related to the async refactoring ([#38](https://github.com/agentuity/sdk-py/pull/38))

## [0.0.81] - 2025-04-29

### Changed
- In production we must bind to 0.0.0.0 ([#37](https://github.com/agentuity/sdk-py/pull/37))

## [0.0.80] - 2025-04-29

### Changed
- Disable openai agents instrumentation for now so we can get past the weird version issue ([#35](https://github.com/agentuity/sdk-py/pull/35))

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

[0.0.100]: https://github.com/agentuity/sdk-py/compare/v0.0.99...v0.0.100
[0.0.99]: https://github.com/agentuity/sdk-py/compare/v0.0.98...v0.0.99
[0.0.98]: https://github.com/agentuity/sdk-py/compare/v0.0.97...v0.0.98
[0.0.97]: https://github.com/agentuity/sdk-py/compare/v0.0.96...v0.0.97
[0.0.96]: https://github.com/agentuity/sdk-py/compare/v0.0.95...v0.0.96
[0.0.95]: https://github.com/agentuity/sdk-py/compare/v0.0.94...v0.0.95
[0.0.94]: https://github.com/agentuity/sdk-py/compare/v0.0.93...v0.0.94
[0.0.93]: https://github.com/agentuity/sdk-py/compare/v0.0.92...v0.0.93
[0.0.92]: https://github.com/agentuity/sdk-py/compare/v0.0.91...v0.0.92
[0.0.91]: https://github.com/agentuity/sdk-py/compare/v0.0.90...v0.0.91
[0.0.90]: https://github.com/agentuity/sdk-py/compare/v0.0.89...v0.0.90
[0.0.89]: https://github.com/agentuity/sdk-py/compare/v0.0.88...v0.0.89
[0.0.88]: https://github.com/agentuity/sdk-py/compare/v0.0.87...v0.0.88
[0.0.87]: https://github.com/agentuity/sdk-py/compare/v0.0.86...v0.0.87
[0.0.86]: https://github.com/agentuity/sdk-py/compare/v0.0.85...v0.0.86
[0.0.85]: https://github.com/agentuity/sdk-py/compare/v0.0.84...v0.0.85
[0.0.84]: https://github.com/agentuity/sdk-py/compare/v0.0.83...v0.0.84
[0.0.83]: https://github.com/agentuity/sdk-py/compare/v0.0.82...v0.0.83
[0.0.82]: https://github.com/agentuity/sdk-py/compare/v0.0.81...v0.0.82
[0.0.81]: https://github.com/agentuity/sdk-py/compare/v0.0.80...v0.0.81
[0.0.80]: https://github.com/agentuity/sdk-py/compare/v0.0.79...v0.0.80
[0.0.79]: https://github.com/agentuity/sdk-py/compare/v0.0.78...v0.0.79
[0.0.78]: https://github.com/agentuity/sdk-py/compare/v0.0.77...v0.0.78
[0.0.77]: https://github.com/agentuity/sdk-py/compare/v0.0.76...v0.0.77
[0.0.76]: https://github.com/agentuity/sdk-py/compare/v0.0.75...v0.0.76
[0.0.75]: https://github.com/agentuity/sdk-py/compare/v0.0.74...v0.0.75
[0.0.74]: https://github.com/agentuity/sdk-py/compare/v0.0.73...v0.0.74
[0.0.73]: https://github.com/agentuity/sdk-py/compare/v0.0.72...v0.0.73
[0.0.72]: https://github.com/agentuity/sdk-py/compare/v0.0.71...v0.0.72
[0.0.71]: https://github.com/agentuity/sdk-py/compare/v0.0.70...v0.0.71
[0.0.70]: https://github.com/agentuity/sdk-py/compare/v0.0.69...v0.0.70
