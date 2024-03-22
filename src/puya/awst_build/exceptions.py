import mypy.nodes

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
