import logging

# filter these out since they create logs loops
exclude_signatures = set(
    [
        "connectionpool._make_request",
        "connectionpool._new_conn",
    ]
)


class ModuleFilter(logging.Filter):
    """Filter out logs from certain modules that create logs loops."""

    def __init__(self):
        super().__init__()

    def filter(self, record):
        key = f"{record.module}.{record.funcName}"
        if key in exclude_signatures:
            return False
        return True
