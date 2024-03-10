import typing

if not typing.TYPE_CHECKING:
    try:
        from puyapy_mocks.itxn import *  # noqa: F403
    except ModuleNotFoundError as ex:
        raise Exception(
            "`puyapy.itxn` cannot be executed by the python interpreter. "
            "It is intended to be used by the puyapy compiler to compile "
            "Algorand Smart Contracts written in Python to TEAL. "
            "For more details see "
            "https://algorandfoundation.github.io/puya/index.html#compiler-usage"
        ) from ex
