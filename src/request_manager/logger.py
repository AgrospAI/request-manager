import logging

logger = logging.getLogger("request_manager")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)


def add_prefix(logger: logging.Logger, prefix: str) -> logging.Logger:
    class PrefixFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            record.msg = f"{prefix} {record.msg}"
            return True

    logger.addFilter(PrefixFilter())
    return logger
