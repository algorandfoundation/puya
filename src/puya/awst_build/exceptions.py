from collections.abc import Sequence

import mypy.nodes

from puya.awst_build import pytypes
from puya.errors import CodeError
from puya.parse import SourceLocation


class UnsupportedASTError(CodeError):
    def __init__(
        self, node: mypy.nodes.Context, location: SourceLocation, *, details: str | None = None
    ):
        msg = f"Unsupported construct {type(node).__name__}"
        if details:
            msg += f": {details}"
        super().__init__(msg, location=location)
        self.details = details


class TypeUnionError(CodeError):
    """Specific instance of CodeError that may be recoverable in some situations"""

    def __init__(self, types: Sequence[pytypes.PyType], location: SourceLocation):
        assert len(types) > 1
        super().__init__(msg="Type unions are unsupported at this location", location=location)
        self.types = types
