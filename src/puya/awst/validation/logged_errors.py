import re

from puya import log
from puya.awst import nodes as awst_nodes
from puya.awst.awst_traverser import AWSTTraverser
from puya.errors import InternalError

logger = log.get_logger(__name__)

_LONG_ERROR_MESSAGE = 64  # long error message (in bytes)
_CAMEL_CASE_RE = re.compile(r"^[a-z0-9]+(?:[A-Z0-9][a-z0-9]+)*$")


class LoggedErrorsValidator(AWSTTraverser):
    """Validates that logged errors are not used in logic signatures,
    and all message layout recommendations in the ARC65 standard"""

    def __init__(self) -> None:
        super().__init__()
        self._in_logic_sig = False

    @classmethod
    def validate(cls, module: awst_nodes.AWST) -> None:
        for module_statement in module:
            validator = cls()
            module_statement.accept(validator)

    def visit_logic_signature(self, statement: awst_nodes.LogicSignature) -> None:
        self._in_logic_sig = True
        super().visit_logic_signature(statement)
        self._in_logic_sig = False

    def visit_assert_expression(self, expr: awst_nodes.AssertExpression) -> None:
        if expr.log_error:
            loc = expr.source_location

            # logicsigs can't log
            if self._in_logic_sig:
                logger.error(
                    "logged errors are not supported in logic signatures",
                    location=loc,
                )

            if expr.error_message:
                # error message format is PREFIX:CODE[:MESSAGE]
                # refer to arc65 for more info
                parts = expr.error_message.split(":")
                prefix: str | None = None
                code: str | None = None
                match parts:
                    case [prefix]:
                        raise InternalError("a prefix only error message is invalid", location=loc)
                    case [prefix, code]:
                        pass
                    # message, if present, should already be valid as it's very permissive
                    case [prefix, code, _]:
                        pass
                    case _:
                        raise InternalError("invalid logged error message", location=loc)

                # ARC65 recommends error codes are alphanumeric and in camelCase
                if code and not code.isalnum():
                    logger.warning("error code should be alphanumeric", location=loc)
                elif code and not _CAMEL_CASE_RE.match(code):
                    logger.warning("error code should be in camelCase", location=loc)

                # AER prefix is reserved for future use
                if prefix == "AER":
                    logger.warning(
                        "AER prefixed error messages are reserved for specific ARC errors",
                        location=loc,
                    )

                # arc65 length recommendations
                msglen = len(expr.error_message)
                if msglen >= _LONG_ERROR_MESSAGE:
                    logger.warning(
                        f"error message is {msglen} bytes long, consider making it shorter",
                        location=loc,
                    )
                elif msglen in (8, 32):
                    logger.warning(
                        f"your final error message is {msglen} bytes long. "
                        "Error messages exactly 8 or 32 bytes long are discouraged",
                        location=loc,
                    )

        super().visit_assert_expression(expr)
