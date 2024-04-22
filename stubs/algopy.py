import typing

if not typing.TYPE_CHECKING:
    raise RuntimeError(
        "`import algopy` cannot be executed by the python interpreter. "
        "It is intended to be used by the puyapy compiler to compile "
        "Algorand smart contracts written in Algorand Python."
        "For more details see "
        "https://algorandfoundation.github.io/puya/index.html#compiler-usage"
    )
