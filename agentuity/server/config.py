class AgentConfig:
    """
    the config for the agent
    """

    def __init__(self, config: dict):
        self._config = config

    @property
    def id(self) -> str:
        """
        the unique id of the agent
        """
        return self._config.get("id")

    @property
    def name(self) -> str:
        """
        the name of the agent
        """
        return self._config.get("name")

    @property
    def description(self) -> str:
        """
        the description of the agent
        """
        return self._config.get("description")

    @property
    def filename(self) -> str:
        """
        the file name to the agent relative to the dist directory
        """
        return self._config.get("filename")

    def __str__(self) -> str:
        return f"AgentConfig(id={self.id}, name={self.name}, description={self.description}, filename={self.filename})"
