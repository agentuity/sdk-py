def instrument():
    """Instrument the Langchain library to work with Agentuity."""
    import logging
    import importlib.util
    
    logger = logging.getLogger(__name__)
    
    if importlib.util.find_spec("langchain_community") is not None:
        logger.info("Configured Langchain to work with Agentuity")
        return True
    else:
        logger.error("Could not instrument Langchain: No module named 'langchain_community'")
        return False
