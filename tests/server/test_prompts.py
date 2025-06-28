"""Tests for the PromptLibrary class."""

import json
import pytest
from unittest.mock import AsyncMock, Mock
from agentuity.server.prompts import (
    PromptLibrary,
    InvalidPromptNameError,
    MissingVariableError,
    PromptNotFoundError,
    PromptExistsError,
)
from agentuity.server.data import DataResult


@pytest.fixture
def mock_kv():
    """Mock KeyValueStore for testing."""
    return AsyncMock()


@pytest.fixture
def mock_tracer():
    """Mock tracer for testing."""
    tracer = Mock()
    span = Mock()
    span.__enter__ = Mock(return_value=span)
    span.__exit__ = Mock(return_value=None)
    tracer.start_as_current_span.return_value = span
    return tracer


@pytest.fixture
def prompt_library(mock_kv, mock_tracer):
    """PromptLibrary instance for testing."""
    return PromptLibrary(kv=mock_kv, tracer=mock_tracer)


class TestPromptNameValidation:
    """Test prompt name validation."""

    def test_valid_names(self, prompt_library):
        """Test that valid names pass validation."""
        valid_names = ["test", "test_prompt", "test-prompt", "TestPrompt123"]
        for name in valid_names:
            prompt_library._validate_prompt_name(name)  # Should not raise

    def test_invalid_names(self, prompt_library):
        """Test that invalid names fail validation."""
        invalid_names = [
            "",  # Empty
            "123test",  # Starts with number
            "test!",  # Invalid character
            "test prompt",  # Space
            "a" * 101,  # Too long
        ]
        for name in invalid_names:
            with pytest.raises(InvalidPromptNameError):
                prompt_library._validate_prompt_name(name)


class TestVariableExtraction:
    """Test variable extraction from templates."""

    def test_extract_variables(self, prompt_library):
        """Test variable extraction."""
        template = "Hello {{name}}, your score is {{score}}. {{name}} again!"
        variables = prompt_library._extract_variables(template)
        assert set(variables) == {"name", "score"}

    def test_no_variables(self, prompt_library):
        """Test template with no variables."""
        template = "Hello world!"
        variables = prompt_library._extract_variables(template)
        assert variables == []

    def test_malformed_variables(self, prompt_library):
        """Test that malformed variables are ignored."""
        template = "Hello {name} and {{ bad_space }} and {{123invalid}}"
        variables = prompt_library._extract_variables(template)
        # bad_space is actually valid (spaces are allowed), but 123invalid starts with number
        assert set(variables) == {"bad_space"}


class TestPromptCreation:
    """Test prompt creation."""

    async def test_create_new_prompt(self, prompt_library, mock_kv):
        """Test creating a new prompt."""
        # Mock no existing prompt
        mock_kv.get.return_value = DataResult(None)

        template = "Hello {{name}}!"
        result = await prompt_library.create(
            name="greeting",
            template=template,
            description="A greeting prompt",
        )

        assert result["template"] == template
        assert result["variables"] == ["name"]
        assert result["version"] == 1
        assert result["description"] == "A greeting prompt"

        # Verify KV calls
        assert mock_kv.set.call_count == 2  # version + metadata

    async def test_create_existing_prompt_without_force(self, prompt_library, mock_kv):
        """Test creating a prompt that already exists without force flag."""
        # Mock existing prompt
        existing_data = {"latest_version": 1}
        mock_data = AsyncMock()
        mock_data.text.return_value = json.dumps(existing_data)
        mock_kv.get.return_value = DataResult(mock_data)

        with pytest.raises(PromptExistsError):
            await prompt_library.create(
                name="existing",
                template="Hello {{name}}!",
            )

    async def test_create_new_version_with_force(self, prompt_library, mock_kv):
        """Test creating a new version with force flag."""
        # Mock existing prompt
        existing_data = {"latest_version": 1, "created_at": "2023-01-01T00:00:00"}
        mock_data = AsyncMock()
        mock_data.text.return_value = json.dumps(existing_data)
        mock_kv.get.return_value = DataResult(mock_data)

        result = await prompt_library.create(
            name="existing",
            template="Hello {{name}} v2!",
            force=True,
        )

        assert result["version"] == 2


class TestPromptRetrieval:
    """Test prompt retrieval."""

    async def test_get_latest_version(self, prompt_library, mock_kv):
        """Test getting the latest version of a prompt."""
        # Mock metadata
        metadata = {"latest_version": 2}
        mock_metadata = AsyncMock()
        mock_metadata.text.return_value = json.dumps(metadata)

        # Mock version data
        version_data = {
            "template": "Hello {{name}}!",
            "variables": ["name"],
            "version": 2,
        }
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)

        mock_kv.get.side_effect = [
            DataResult(mock_metadata),  # metadata call
            DataResult(mock_version),  # version call
        ]

        result = await prompt_library.get("test")
        assert result == version_data

    async def test_get_specific_version(self, prompt_library, mock_kv):
        """Test getting a specific version of a prompt."""
        version_data = {
            "template": "Hello {{name}}!",
            "variables": ["name"],
            "version": 1,
        }
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)
        mock_kv.get.return_value = DataResult(mock_version)

        result = await prompt_library.get("test", version=1)
        assert result == version_data

    async def test_get_nonexistent_prompt(self, prompt_library, mock_kv):
        """Test getting a prompt that doesn't exist."""
        mock_kv.get.return_value = DataResult(None)

        with pytest.raises(PromptNotFoundError):
            await prompt_library.get("nonexistent")


class TestPromptCompilation:
    """Test prompt template compilation."""

    async def test_compile_with_all_variables(self, prompt_library, mock_kv):
        """Test compiling a prompt with all required variables."""
        version_data = {
            "template": "Hello {{name}}, your score is {{score}}!",
            "variables": ["name", "score"],
        }
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)
        mock_kv.get.return_value = DataResult(mock_version)

        result = await prompt_library.compile(
            "test",
            {"name": "Alice", "score": 95},
            version=1,  # Specify version to avoid metadata lookup
        )

        assert result == "Hello Alice, your score is 95!"

    async def test_compile_with_missing_variables(self, prompt_library, mock_kv):
        """Test compiling a prompt with missing variables."""
        version_data = {
            "template": "Hello {{name}}, your score is {{score}}!",
            "variables": ["name", "score"],
        }
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)
        mock_kv.get.return_value = DataResult(mock_version)

        with pytest.raises(MissingVariableError) as exc_info:
            await prompt_library.compile("test", {"name": "Alice"}, version=1)

        assert "score" in str(exc_info.value)

    async def test_compile_with_extra_variables(self, prompt_library, mock_kv):
        """Test compiling a prompt with extra variables (should work)."""
        version_data = {
            "template": "Hello {{name}}!",
            "variables": ["name"],
        }
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)
        mock_kv.get.return_value = DataResult(mock_version)

        result = await prompt_library.compile(
            "test",
            {"name": "Alice", "extra": "ignored"},
            version=1,  # Specify version to avoid metadata lookup
        )

        assert result == "Hello Alice!"


class TestPromptDeletion:
    """Test prompt deletion."""

    async def test_delete_all_versions(self, prompt_library, mock_kv):
        """Test deleting all versions of a prompt."""
        # Mock metadata
        metadata = {"total_versions": 2}
        mock_metadata = AsyncMock()
        mock_metadata.text.return_value = json.dumps(metadata)
        mock_kv.get.return_value = DataResult(mock_metadata)

        await prompt_library.delete("test")

        # Should delete all versions plus metadata
        assert mock_kv.delete.call_count == 3  # v1, v2, metadata

    async def test_delete_specific_version(self, prompt_library, mock_kv):
        """Test deleting a specific version of a prompt."""
        version_data = {"version": 1}
        mock_version = AsyncMock()
        mock_version.text.return_value = json.dumps(version_data)

        metadata = {"total_versions": 2}
        mock_metadata = AsyncMock()
        mock_metadata.text.return_value = json.dumps(metadata)

        mock_kv.get.side_effect = [
            DataResult(mock_version),  # version check
            DataResult(mock_metadata),  # metadata update
            DataResult(mock_metadata),  # versions call
        ]

        await prompt_library.delete("test", version=1)

        # Should delete one version and update metadata
        assert mock_kv.delete.call_count == 1
        assert mock_kv.set.call_count == 1  # metadata update


class TestPromptCopy:
    """Test prompt copying."""

    async def test_copy_prompt(self, prompt_library, mock_kv):
        """Test copying a prompt to a new name."""
        source_data = {
            "template": "Hello {{name}}!",
            "variables": ["name"],
            "description": "Original prompt",
            "config": {"model": "gpt-4"},
        }
        mock_source = AsyncMock()
        mock_source.text.return_value = json.dumps(source_data)

        # Mock calls: get source, check if target exists, create target
        mock_kv.get.side_effect = [
            DataResult(mock_source),  # get source
            DataResult(None),  # target doesn't exist
        ]

        result = await prompt_library.copy("source", "target", version=1)

        assert result["template"] == source_data["template"]
        assert result["description"] == source_data["description"]
        assert result["config"] == source_data["config"]
        assert result["version"] == 1  # new prompt starts at version 1


class TestPromptVersions:
    """Test prompt version management."""

    async def test_get_versions(self, prompt_library, mock_kv):
        """Test getting all versions of a prompt."""
        metadata = {"total_versions": 3}
        mock_metadata = AsyncMock()
        mock_metadata.text.return_value = json.dumps(metadata)
        mock_kv.get.return_value = DataResult(mock_metadata)

        versions = await prompt_library.versions("test")
        assert versions == [1, 2, 3]

    async def test_get_versions_nonexistent(self, prompt_library, mock_kv):
        """Test getting versions of a nonexistent prompt."""
        mock_kv.get.return_value = DataResult(None)

        with pytest.raises(PromptNotFoundError):
            await prompt_library.versions("nonexistent")


class TestConfigUpdate:
    """Test prompt configuration updates."""

    async def test_update_config(self, prompt_library, mock_kv):
        """Test updating prompt configuration."""
        existing_data = {
            "template": "Hello {{name}}!",
            "config": {"model": "gpt-3.5"},
            "version": 1,
        }
        mock_data = AsyncMock()
        mock_data.text.return_value = json.dumps(existing_data)
        mock_kv.get.return_value = DataResult(mock_data)

        result = await prompt_library.update_config(
            "test",
            {"temperature": 0.7, "model": "gpt-4"},
            version=1,  # Specify version to avoid metadata lookup
        )

        # Should merge configs
        assert result["config"]["model"] == "gpt-4"
        assert result["config"]["temperature"] == 0.7
        assert "updated_at" in result
