import pytest
from wyvern.logging_config import LogLevel, configure_logging


@pytest.fixture(autouse=True, scope="session")
def _setup_logging() -> None:
    # configure logging for tests
    # note cache_logger should be False if calling configure_logging more than once
    configure_logging(min_log_level=LogLevel.notset, cache_logger=False)
