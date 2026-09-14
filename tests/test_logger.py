import logging

from request_manager import logger as log


MSG = "Hello world"


def test_add_prefix_works(caplog):
    logger = logging.getLogger()
    logger = log.add_prefix(logger, "TEST")

    with caplog.at_level(logging.INFO):
        logger.info(MSG)

    assert "TEST" in caplog.text
    assert MSG in caplog.text
