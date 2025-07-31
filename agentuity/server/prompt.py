import httpx
import logging
from typing import Optional, Dict, Any
from opentelemetry.propagate import inject
from agentuity import __version__
from opentelemetry import trace

logger = logging.getLogger(__name__)


class CompilePromptRequest:
    """Request model for prompt compilation."""

    def __init__(
        self, name: str, variables: Dict[str, Any], version: Optional[int] = None
    ):
        self.name = name
        self.variables = variables
        self.version = version

    def to_dict(self) -> Dict[str, Any]:
        data = {"name": self.name, "variables": self.variables}
        if self.version is not None:
            data["version"] = self.version
        return data


class CompilePromptData:
    """Data model for compiled prompt response."""

    def __init__(self, compiled_content: str, prompt_id: str, version: int):
        self.compiled_content = compiled_content
        self.prompt_id = prompt_id
        self.version = version

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CompilePromptData":
        return cls(
            compiled_content=data["compiledContent"],
            prompt_id=data["promptId"],
            version=data["version"],
        )


class CompilePromptResponse:
    """Response model for prompt compilation."""

    def __init__(
        self,
        success: bool,
        data: Optional[CompilePromptData] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.data = data
        self.error = error

    @classmethod
    def from_dict(cls, response_data: Dict[str, Any]) -> "CompilePromptResponse":
        success = response_data.get("success", False)
        error = response_data.get("error")
        data = None

        if success and "data" in response_data:
            data = CompilePromptData.from_dict(response_data["data"])

        return cls(success=success, data=data, error=error)


class PromptCompileResult:
    """Result container for prompt compilation."""

    def __init__(self, compiled_content: str, prompt_id: str, version: int):
        self.compiled_content = compiled_content
        self.prompt_id = prompt_id
        self.version = version

    def __str__(self) -> str:
        return self.compiled_content


class PromptClient:
    """
    A prompt client for compiling prompt templates with variables. This class provides
    methods to interact with the Agentuity prompt management service, supporting
    template compilation with variable substitution and version management.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        tracer: trace.Tracer,
    ):
        """
        Initialize the PromptClient.

        Args:
            base_url: The base URL of the Agentuity Cloud service
            api_key: The API key for authentication
            tracer: OpenTelemetry tracer for distributed tracing
        """
        self.base_url = base_url
        self.api_key = api_key
        self.tracer = tracer

    async def compile(
        self, name: str, variables: Dict[str, Any], version: Optional[int] = None
    ) -> PromptCompileResult:
        """
        Compile a prompt template with the provided variables.

        Args:
            name: The name of the prompt template
            variables: Dictionary of variables to substitute in the template
            version: Optional specific version to compile (defaults to active version)

        Returns:
            PromptCompileResult: The compiled prompt with metadata

        Raises:
            ValueError: If the prompt name is invalid or variables are malformed
            Exception: If the compilation fails or the prompt is not found
        """
        with self.tracer.start_as_current_span("agentuity.prompt.compile") as span:
            span.set_attribute("prompt.name", name)
            span.set_attribute("prompt.variables_count", len(variables))
            if version is not None:
                span.set_attribute("prompt.version", version)

            # Validate inputs
            if not name or not isinstance(name, str):
                raise ValueError("Prompt name must be a non-empty string")

            if not isinstance(variables, dict):
                raise ValueError("Variables must be a dictionary")

            if version is not None and (not isinstance(version, int) or version < 1):
                raise ValueError("Version must be a positive integer")

            # Prepare request
            request = CompilePromptRequest(
                name=name, variables=variables, version=version
            )

            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": f"Agentuity Python SDK/{__version__}",
                "Content-Type": "application/json",
            }
            inject(headers)

            # Construct the URL and log it for debugging
            url = f"{self.base_url}/prompt/2025-03-17/compile"
            logger.debug(f"Making prompt compile request to: {url}")
            logger.debug(f"Request payload: {request.to_dict()}")

            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        url,
                        headers=headers,
                        json=request.to_dict(),
                    )

                # Log response details for debugging
                logger.debug(f"Received response: HTTP {response.status_code}")
                logger.debug(f"Response headers: {dict(response.headers)}")

                # Parse response with better error handling
                try:
                    if not response.content:
                        error_msg = f"Empty response from prompt service at {url} (HTTP {response.status_code})"
                        logger.error(error_msg)
                        raise Exception(error_msg)

                    logger.debug(
                        f"Response content length: {len(response.content)} bytes"
                    )
                    response_data = response.json()
                except Exception as json_error:
                    error_msg = f"Failed to parse JSON response from prompt service at {url} (HTTP {response.status_code})"
                    if response.content:
                        # Include first 200 chars of response for debugging
                        content_preview = response.content.decode(
                            "utf-8", errors="ignore"
                        )[:200]
                        error_msg += f". Response content: {content_preview}"
                        logger.error(f"Invalid JSON response: {content_preview}")
                    else:
                        error_msg += ". Response was empty."
                        logger.error("Received empty response from prompt service")

                    span.set_status(trace.StatusCode.ERROR, error_msg)
                    raise Exception(error_msg) from json_error

                compile_response = CompilePromptResponse.from_dict(response_data)

                if response.status_code == 200:
                    if compile_response.success and compile_response.data:
                        span.set_status(trace.StatusCode.OK)
                        span.set_attribute(
                            "prompt.id", compile_response.data.prompt_id
                        )
                        span.set_attribute(
                            "prompt.compiled_version", compile_response.data.version
                        )

                        return PromptCompileResult(
                            compiled_content=compile_response.data.compiled_content,
                            prompt_id=compile_response.data.prompt_id,
                            version=compile_response.data.version,
                        )
                    else:
                        error_msg = (
                            compile_response.error
                            or "Unknown error during compilation"
                        )
                        span.set_status(trace.StatusCode.ERROR, error_msg)
                        raise Exception(f"Prompt compilation failed: {error_msg}")
                else:
                    error_msg = compile_response.error or response.text
                    span.set_status(trace.StatusCode.ERROR, "Failed to compile prompt")
                    span.record_exception(Exception(error_msg))
                    raise Exception(f"Failed to compile prompt: {response.status_code}")

            except httpx.RequestError as e:
                span.set_status(trace.StatusCode.ERROR, str(e))
                span.record_exception(e)
                raise Exception(f"Failed to connect to prompt service: {e}")
            except Exception as e:
                if not span.status.status_code == trace.StatusCode.ERROR:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    span.record_exception(e)
                raise
