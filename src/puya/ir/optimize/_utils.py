import typing
from collections.abc import Sequence

from puya.errors import InternalError
from puya.ir import models
from puya.ir.visitor import IRTraverser


def get_definition(
    subroutine: models.Subroutine, register: models.Register, *, should_exist: bool = True
) -> models.Assignment | models.Phi | None:
    if register in subroutine.parameters:
        return None
    for block in subroutine.body:
        for phi in block.phis:
            if phi.register == register:
                return phi
        for op in block.ops:
            if isinstance(op, models.Assignment) and register in op.targets:
                return op
    if should_exist:
        raise InternalError(f"Register is not defined: {register}", subroutine.source_location)
    return None


class _HighLevelOpError(Exception):
    pass


class HasHighLevelOps(IRTraverser):
    @classmethod
    def check(cls, body: Sequence[models.BasicBlock]) -> bool:
        try:
            HasHighLevelOps().visit_all_blocks(body)
        except _HighLevelOpError:
            return True
        return False

    @typing.override
    def visit_box_read(self, read: models.BoxRead) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_box_write(self, write: models.BoxWrite) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_array_length(self, length: models.ArrayLength) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_extract_value(self, read: models.ExtractValue) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_replace_value(self, write: models.ReplaceValue) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_bytes_encode(self, encode: models.BytesEncode) -> None:
        raise _HighLevelOpError

    @typing.override
    def visit_decode_bytes(self, decode: models.DecodeBytes) -> None:
        raise _HighLevelOpError
