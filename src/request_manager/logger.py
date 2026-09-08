import logging

logger = logging.getLogger("request_manager")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)


def add_prefix(logger: logging.Logger, prefix: str) -> logging.Logger:
    new_logger = logging.Logger(logger.name, level=logger.level)
    new_logger.handlers = list(logger.handlers)
    new_logger.filters = list(logger.filters)
    new_logger.propagate = logger.propagate
    new_logger.parent = logger.parent
    new_logger.disabled = logger.disabled

    class PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.msg = f"{prefix} {record.msg}"
            return True

    new_logger.addFilter(PrefixFilter())
    return new_logger
