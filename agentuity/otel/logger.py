import logging


def create_logger(
    logger: logging.Logger, name: str, attributes: dict
) -> logging.Logger:
    """
    Create a child logger with the given attributes.

    Args:
        logger: The parent logger
        name: The name of the child logger
        attributes: The attributes to add to the child logger

    Returns:
        The child logger
    """
    child = logger.getChild(name)

    class ContextFilter(logging.Filter):
        def filter(self, record):
            # Add the attributes directly to the record
            for key, value in attributes.items():
                setattr(record, key, value)
            return True

    child.addFilter(ContextFilter())
    return child
