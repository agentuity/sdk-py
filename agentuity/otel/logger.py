import logging
from typing import List


# Global list of user logger providers for multi-delegate logging
_user_logger_providers: List = []


def add_user_logger_provider(provider):
    """Add a user logger provider to the multi-delegate system."""
    global _user_logger_providers
    _user_logger_providers.append(provider)
    logging.info("Added user logger provider to multi-delegate system")


def emit_to_user_providers(record: logging.LogRecord):
    """Emit a log record to all user logger providers."""
    if not _user_logger_providers:
        return
        
    for provider in _user_logger_providers:
        try:
            # Get a logger from the provider and emit the record
            otel_logger = provider.get_logger(__name__)
            
            # Convert log level to OpenTelemetry severity
            from opentelemetry._logs import SeverityNumber
            
            severity_map = {
                logging.DEBUG: SeverityNumber.DEBUG,
                logging.INFO: SeverityNumber.INFO,
                logging.WARNING: SeverityNumber.WARN,
                logging.ERROR: SeverityNumber.ERROR,
                logging.CRITICAL: SeverityNumber.FATAL,
            }
            
            severity = severity_map.get(record.levelno, SeverityNumber.INFO)
            
            # Create attributes from record
            attributes = {
                "source": "agentuity-sdk",
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            
            # Add any custom attributes from the record
            for key, value in record.__dict__.items():
                if not key.startswith('_') and key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename', 'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated', 'thread', 'threadName', 'processName', 'process']:
                    attributes[key] = value
            
            # Emit the log record
            otel_logger.emit(
                severity_number=severity,
                body=record.getMessage(),
                attributes=attributes,
                timestamp=int(record.created * 1_000_000_000)  # Convert to nanoseconds
            )
            
        except Exception as e:
            # Don't let user logger errors break the main logging
            logging.warning(f"Error emitting to user logger provider: {e}")


class MultiDelegateHandler(logging.Handler):
    """A logging handler that emits to user OTEL providers in addition to normal logging."""
    
    def emit(self, record: logging.LogRecord):
        """Emit the record to user logger providers."""
        emit_to_user_providers(record)


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
    
    # Add the multi-delegate handler if we have user providers
    if _user_logger_providers and not any(isinstance(h, MultiDelegateHandler) for h in child.handlers):
        multi_handler = MultiDelegateHandler()
        multi_handler.setLevel(logging.DEBUG)  # Capture all levels
        child.addHandler(multi_handler)
    
    return child
