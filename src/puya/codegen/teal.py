from collections.abc import Sequence

import attrs

from puya.codegen.utils import format_bytes
from puya.ir.types_ import AVMBytesEncoding


@attrs.frozen(str=False, kw_only=True)
class TealOp:
    op_code: str
    comment: str | None = attrs.field(default=None)
    """A comment that is always emitted, should only be used for user comments related to an
    op such as assert or err"""

    @property
    def immediates(self) -> Sequence[int | str]:
        return ()

    def __str__(self) -> str:
        return self.teal_str(self.op_code, *self.immediates)

    def teal_str(self, op_code: str, *immediates: int | str) -> str:
        teal_args = [op_code, *map(str, immediates)]
        if self.comment:
            teal_args.append(f"// {self.comment}")
        return " ".join(teal_args)


@attrs.frozen
class Dup(TealOp):
    op_code: str = attrs.field(default="dup", init=False)


@attrs.frozen
class Pop(TealOp):
    op_code: str = attrs.field(default="pop", init=False)


@attrs.frozen
class RetSub(TealOp):
    op_code: str = attrs.field(default="retsub", init=False)


@attrs.frozen
class TealOpN(TealOp):
    n: int

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.n,)


@attrs.frozen
class Cover(TealOpN):
    op_code: str = attrs.field(default="cover", init=False)

    def __str__(self) -> str:
        if self.n == 1:
            return self.teal_str("swap")
        else:
            return super().__str__()


@attrs.frozen
class Uncover(TealOpN):
    op_code: str = attrs.field(default="uncover", init=False)

    def __str__(self) -> str:
        if self.n == 1:
            return self.teal_str("swap")
        else:
            return super().__str__()


@attrs.frozen
class Dig(TealOpN):
    op_code: str = attrs.field(default="dig", init=False)


@attrs.frozen
class Bury(TealOpN):
    op_code: str = attrs.field(default="bury", init=False)


@attrs.frozen
class FrameDig(TealOpN):
    op_code: str = attrs.field(default="frame_dig", init=False)


@attrs.frozen
class FrameBury(TealOpN):
    op_code: str = attrs.field(default="frame_bury", init=False)


@attrs.frozen
class PushInt(TealOp):
    n: int | str
    op_code: str = attrs.field(default="int", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.n,)


@attrs.frozen
class PopN(TealOpN):
    op_code: str = attrs.field(default="popn", init=False)


@attrs.frozen
class DupN(TealOpN):
    op_code: str = attrs.field(default="dupn", init=False)


@attrs.frozen
class Proto(TealOp):
    parameters: int
    returns: int
    op_code: str = attrs.field(default="proto", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return self.parameters, self.returns


@attrs.frozen
class PushBytes(TealOp):
    n: bytes
    encoding: AVMBytesEncoding
    op_code: str = attrs.field(default="byte", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        bytes_str = format_bytes(self.n, self.encoding)
        if self.encoding in (
            AVMBytesEncoding.utf8,
            AVMBytesEncoding.base16,
        ):
            return (bytes_str,)
        hint = self.encoding.name
        return hint, bytes_str


@attrs.frozen
class PushAddress(TealOp):
    a: str
    op_code: str = attrs.field(default="addr", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.a,)


@attrs.frozen
class PushMethod(TealOp):
    a: str
    op_code: str = attrs.field(default="method", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (f'"{self.a}"',)


@attrs.frozen
class Intrinsic(TealOp):
    immediates: Sequence[int | str]


@attrs.frozen
class CallSub(TealOp):
    target: str
    op_code: str = attrs.field(default="callsub", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.target,)
