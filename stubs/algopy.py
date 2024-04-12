import logging
import typing

logger = logging.getLogger(__name__)

if not typing.TYPE_CHECKING:
    import importlib

    if importlib.util.find_spec("algopy_testing"):
        # If the module is not found, print a warning message to stderr, but do not fail the process
        try:
            from algopy_testing import *  # noqa: F403

        except ImportError as e:
            raise RuntimeError(
                "`algorand-python` testing module is not installed. "
                "Install via `pip install algorand-python[testing]` "
                "or in accordance with your package manager."
            ) from e
    else:
        raise RuntimeError(
            "`import algopy` cannot be executed by the python interpreter. "
            "It is intended to be used by the puyapy compiler to compile "
            "Algorand smart contracts written in Algorand Python. "
            "For more details see "
            "https://algorandfoundation.github.io/puya/index.html#compiler-usage"
        )
