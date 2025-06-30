"""
Core PromptLibrary class for managing prompts with Agentuity's KV store.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from opentelemetry import trace

from .keyvalue import KeyValueStore


class InvalidPromptNameError(Exception):
    """Raised when a prompt name is invalid."""

    def __init__(self, name: str, reason: str):
        self.name = name
        self.reason = reason
        super().__init__(f"Invalid prompt name '{name}': {reason}")


class MissingVariableError(Exception):
    """Raised when required variables are missing from template compilation."""

    def __init__(self, missing_variables: List[str], prompt_name: str):
        self.missing_variables = missing_variables
        self.prompt_name = prompt_name
        super().__init__(
            f"Missing required variables for prompt '{prompt_name}': {', '.join(missing_variables)}"
        )


class PromptNotFoundError(Exception):
    """Raised when a prompt is not found."""

    def __init__(self, name: str, version: Optional[int] = None):
        self.name = name
        self.version = version
        if version:
            super().__init__(f"Prompt '{name}' version {version} not found")
        else:
            super().__init__(f"Prompt '{name}' not found")


class PromptExistsError(Exception):
    """Raised when attempting to create a prompt that already exists."""

    def __init__(self, name: str, current_version: int):
        self.name = name
        self.current_version = current_version
        super().__init__(
            f"Prompt '{name}' already exists with version {current_version}. Use force=True to create a new version."
        )


class PromptLibrary:
    """
    A prompt library for managing versioned prompt templates using Agentuity's KV store.

    This class provides methods to create, retrieve, compile, and manage prompt templates
    with automatic versioning and variable extraction. User scoping is handled by the
    underlying KV store API based on authentication.
    """

    def __init__(self, kv: KeyValueStore, tracer: trace.Tracer):
        """
        Initialize the PromptLibrary.

        Args:
            kv: KeyValueStore instance for persistence
            tracer: OpenTelemetry tracer for observability
        """
        self.kv = kv
        self.tracer = tracer

    def _validate_prompt_name(self, name: str) -> None:
        """
        Validate that a prompt name follows the required conventions.

        Args:
            name: The prompt name to validate.

        Raises:
            InvalidPromptNameError: If the name is invalid.
        """
        if not name:
            raise InvalidPromptNameError(name, "name cannot be empty")

        if not re.match(r"^[a-zA-Z][a-zA-Z0-9_-]*$", name):
            raise InvalidPromptNameError(
                name,
                "name must start with a letter and contain only letters, numbers, underscores, and hyphens",
            )

        if len(name) > 100:
            raise InvalidPromptNameError(
                name, "name cannot be longer than 100 characters"
            )

    def _extract_variables(self, template: str) -> List[str]:
        """
        Extract variable names from a template using {{variable}} syntax.

        Args:
            template: The template string to analyze.

        Returns:
            List of unique variable names found in the template.
        """
        # Find all {{variable}} patterns
        pattern = r"\{\{\s*([a-zA-Z][a-zA-Z0-9_]*)\s*\}\}"
        matches = re.findall(pattern, template)
        return list(set(matches))  # Remove duplicates

    def _get_prompt_key(self, name: str) -> str:
        """Get the KV key for a prompt's metadata."""
        return f"prompts:{name}"

    def _get_version_key(self, name: str, version: int) -> str:
        """Get the KV key for a specific prompt version."""
        return f"prompts:{name}:v{version}"

    async def create(
        self,
        name: str,
        template: str,
        description: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        force: bool = False,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Create a new prompt template. Raises an error if the prompt already exists.

        Args:
            name: The prompt name.
            template: The prompt template with {{variable}} placeholders.
            description: Optional description of the prompt.
            config: Optional configuration dict (e.g., model settings).
            force: If True, allows creating a new version of an existing prompt.
            **kwargs: Additional metadata to store with the prompt.

        Returns:
            Dict containing the created prompt metadata including version number.

        Raises:
            InvalidPromptNameError: If the prompt name is invalid.
            PromptExistsError: If the prompt already exists and force=False.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.create") as span:
            span.set_attribute("prompt.name", name)

            self._validate_prompt_name(name)

            # Get current prompt metadata to determine next version
            prompt_key = self._get_prompt_key(name)
            current_data = await self.kv.get("prompts", prompt_key)

            if current_data.data:
                current_metadata = json.loads(await current_data.data.text())
                if not force:
                    # Prompt exists and we're not forcing - raise error
                    raise PromptExistsError(name, current_metadata["latest_version"])
                next_version = current_metadata["latest_version"] + 1
            else:
                next_version = 1

            span.set_attribute("prompt.version", next_version)

            # Extract variables from template
            variables = self._extract_variables(template)
            span.set_attribute("prompt.variables", variables)

            # Create version data
            version_data = {
                "template": template,
                "variables": variables,
                "description": description,
                "config": config or {},
                "created_at": datetime.utcnow().isoformat(),
                "version": next_version,
                **kwargs,
            }

            # Store the version
            version_key = self._get_version_key(name, next_version)
            await self.kv.set("prompts", version_key, json.dumps(version_data))

            # Update prompt metadata
            prompt_metadata = {
                "name": name,
                "latest_version": next_version,
                "created_at": current_metadata.get(
                    "created_at", datetime.utcnow().isoformat()
                )
                if current_data.data
                else datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat(),
                "total_versions": next_version,
            }

            await self.kv.set("prompts", prompt_key, json.dumps(prompt_metadata))

            span.set_status(trace.StatusCode.OK)
            return version_data

    async def get(self, name: str, version: Optional[int] = None) -> Dict[str, Any]:
        """
        Get a prompt by name and optional version.

        Args:
            name: The prompt name.
            version: Optional version number. If not provided, returns latest version.

        Returns:
            Dict containing the prompt data.

        Raises:
            PromptNotFoundError: If the prompt or version doesn't exist.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.get") as span:
            span.set_attribute("prompt.name", name)

            self._validate_prompt_name(name)

            # Get prompt metadata to find latest version if not specified
            if version is None:
                prompt_key = self._get_prompt_key(name)
                metadata_result = await self.kv.get("prompts", prompt_key)

                if not metadata_result.data:
                    raise PromptNotFoundError(name)

                metadata = json.loads(await metadata_result.data.text())
                version = metadata["latest_version"]

            span.set_attribute("prompt.version", version)

            # Get the specific version
            version_key = self._get_version_key(name, version)
            version_result = await self.kv.get("prompts", version_key)

            if not version_result.data:
                raise PromptNotFoundError(name, version)

            span.set_status(trace.StatusCode.OK)
            return json.loads(await version_result.data.text())

    async def compile(
        self, name: str, variables: Dict[str, Any], version: Optional[int] = None
    ) -> str:
        """
        Compile a prompt template with the provided variables.

        Args:
            name: The prompt name.
            variables: Dict of variable names to values.
            version: Optional version number. If not provided, uses latest version.

        Returns:
            The compiled prompt string with variables substituted.

        Raises:
            PromptNotFoundError: If the prompt doesn't exist.
            MissingVariableError: If required variables are missing.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.compile") as span:
            span.set_attribute("prompt.name", name)

            prompt_data = await self.get(name, version)

            template = prompt_data["template"]
            required_variables = set(prompt_data["variables"])
            provided_variables = set(variables.keys())

            missing_variables = required_variables - provided_variables
            if missing_variables:
                raise MissingVariableError(list(missing_variables), name)

            span.set_attribute("prompt.variables", list(provided_variables))

            # Replace variables in template
            compiled_template = template
            for var_name, var_value in variables.items():
                # Replace {{variable}} with the actual value
                pattern = r"\{\{\s*" + re.escape(var_name) + r"\s*\}\}"
                compiled_template = re.sub(pattern, str(var_value), compiled_template)

            span.set_status(trace.StatusCode.OK)
            return compiled_template

    async def versions(self, name: str) -> List[int]:
        """
        Get all available versions for a prompt.

        Args:
            name: The prompt name.

        Returns:
            List of version numbers sorted in ascending order.

        Raises:
            PromptNotFoundError: If the prompt doesn't exist.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.versions") as span:
            span.set_attribute("prompt.name", name)

            self._validate_prompt_name(name)

            # Get prompt metadata
            prompt_key = self._get_prompt_key(name)
            metadata_result = await self.kv.get("prompts", prompt_key)

            if not metadata_result.data:
                raise PromptNotFoundError(name)

            metadata = json.loads(await metadata_result.data.text())
            total_versions = metadata["total_versions"]

            versions_list = list(range(1, total_versions + 1))
            span.set_attribute("prompt.total_versions", total_versions)
            span.set_status(trace.StatusCode.OK)

            return versions_list

    async def delete(self, name: str, version: Optional[int] = None) -> None:
        """
        Delete a prompt or specific version.

        Args:
            name: The prompt name.
            version: Optional version number. If not provided, deletes all versions.

        Raises:
            PromptNotFoundError: If the prompt doesn't exist.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.delete") as span:
            span.set_attribute("prompt.name", name)

            self._validate_prompt_name(name)

            if version is None:
                # Delete all versions
                available_versions = await self.versions(name)

                # Delete all version data
                for v in available_versions:
                    version_key = self._get_version_key(name, v)
                    await self.kv.delete("prompts", version_key)

                # Delete prompt metadata
                prompt_key = self._get_prompt_key(name)
                await self.kv.delete("prompts", prompt_key)

                span.set_attribute("prompt.deleted_versions", len(available_versions))
            else:
                # Delete specific version
                span.set_attribute("prompt.version", version)
                version_key = self._get_version_key(name, version)
                version_result = await self.kv.get("prompts", version_key)

                if not version_result.data:
                    raise PromptNotFoundError(name, version)

                await self.kv.delete("prompts", version_key)

                # Update metadata
                prompt_key = self._get_prompt_key(name)
                metadata_result = await self.kv.get("prompts", prompt_key)

                if metadata_result.data:
                    metadata = json.loads(await metadata_result.data.text())
                    available_versions = await self.versions(name)

                    if available_versions:
                        metadata["latest_version"] = max(available_versions)
                        metadata["total_versions"] = len(available_versions)
                        metadata["updated_at"] = datetime.utcnow().isoformat()
                        await self.kv.set("prompts", prompt_key, json.dumps(metadata))
                    else:
                        # No versions left, delete metadata
                        await self.kv.delete("prompts", prompt_key)

            span.set_status(trace.StatusCode.OK)

    async def update_config(
        self, name: str, config: Dict[str, Any], version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Update the configuration for a prompt version.

        Args:
            name: The prompt name.
            config: New configuration dict to merge with existing config.
            version: Optional version number. If not provided, uses latest version.

        Returns:
            Updated prompt data.

        Raises:
            PromptNotFoundError: If the prompt doesn't exist.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.update_config") as span:
            span.set_attribute("prompt.name", name)

            prompt_data = await self.get(name, version)

            # Merge configurations
            existing_config = prompt_data.get("config", {})
            existing_config.update(config)
            prompt_data["config"] = existing_config
            prompt_data["updated_at"] = datetime.utcnow().isoformat()

            # Save updated version
            version_num = prompt_data["version"]
            span.set_attribute("prompt.version", version_num)
            version_key = self._get_version_key(name, version_num)
            await self.kv.set("prompts", version_key, json.dumps(prompt_data))

            span.set_status(trace.StatusCode.OK)
            return prompt_data

    async def copy(
        self, source_name: str, target_name: str, version: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Copy a prompt to a new name.

        Args:
            source_name: The source prompt name.
            target_name: The target prompt name.
            version: Optional version to copy. If not provided, copies latest version.

        Returns:
            The created prompt data.

        Raises:
            PromptNotFoundError: If the source prompt doesn't exist.
            InvalidPromptNameError: If the target name is invalid.
        """
        with self.tracer.start_as_current_span("agentuity.prompt.copy") as span:
            span.set_attribute("prompt.source_name", source_name)
            span.set_attribute("prompt.target_name", target_name)

            source_data = await self.get(source_name, version)

            # Create new prompt with copied data
            result = await self.create(
                name=target_name,
                template=source_data["template"],
                description=source_data.get("description"),
                config=source_data.get("config", {}),
            )

            span.set_status(trace.StatusCode.OK)
            return result
