class AgentConfig:
    """
    Configuration class for an agent. This class provides a structured way to access
    agent configuration properties including ID, name, description, and filename.
    """

    def __init__(self, config: dict):
        """
        Initialize the AgentConfig with a configuration dictionary.

        Args:
            config: Dictionary containing agent configuration with the following keys:
                - id: Unique identifier for the agent
                - name: Display name of the agent
                - description: Description of the agent's purpose
                - filename: Path to the agent's file relative to the dist directory
        """
        self._config = config

    @property
    def id(self) -> str:
        """
        Get the unique identifier of the agent.

        Returns:
            str: The unique identifier of the agent, or None if not set
        """
        return self._config.get("id")

    @property
    def name(self) -> str:
        """
        Get the display name of the agent.

        Returns:
            str: The display name of the agent, or None if not set
        """
        return self._config.get("name")

    @property
    def description(self) -> str:
        """
        Get the description of the agent.

        Returns:
            str: The description of the agent's purpose, or None if not set
        """
        return self._config.get("description")

    @property
    def filename(self) -> str:
        """
        Get the filename of the agent relative to the dist directory.

        Returns:
            str: The path to the agent's file relative to the dist directory, or None if not set
        """
        return self._config.get("filename")

    def __str__(self) -> str:
        """
        Get a string representation of the agent configuration.

        Returns:
            str: A formatted string containing all agent configuration properties
        """
        return f"AgentConfig(id={self.id}, name={self.name}, description={self.description}, filename={self.filename})"
