import logging

logger = logging.getLogger("request_manager")


def setup_logging() -> None:
    logging.basicConfig(level=logging.INFO)
