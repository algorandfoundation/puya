from puya.errors import CodeError
from puya.parse import SourceLocation


class UnsupportedASTError(CodeError):
    def __init__(self, location: SourceLocation, *, details: str | None = None):
        msg = f"Unsupported construct {location.mypy_src_node}"
        if details:
            msg += f": {details}"
        super().__init__(msg, location=location)
        self.details = details
