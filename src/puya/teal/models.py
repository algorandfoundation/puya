from collections.abc import Iterable, Sequence

import attrs

from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.utils import format_bytes
from puya.parse import SourceLocation


@attrs.frozen(str=False, kw_only=True)
class TealOp:
    op_code: str
    consumes: int
    produces: int
    source_location: SourceLocation | None = attrs.field(eq=False)
    comment: str | None = None
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

    @property
    def stack_height_delta(self) -> int:
        return self.produces - self.consumes


@attrs.frozen
class Dup(TealOp):
    op_code: str = attrs.field(default="dup", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=2, init=False)


@attrs.frozen
class Dup2(TealOp):
    op_code: str = attrs.field(default="dup2", init=False)
    consumes: int = attrs.field(default=2, init=False)
    produces: int = attrs.field(default=4, init=False)


@attrs.frozen
class Pop(TealOp):
    op_code: str = attrs.field(default="pop", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)


@attrs.frozen
class RetSub(TealOp):
    op_code: str = attrs.field(default="retsub", init=False)
    produces: int = attrs.field(default=0, init=False)


@attrs.frozen
class TealOpN(TealOp):
    n: int

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.n,)


@attrs.frozen
class Cover(TealOpN):
    op_code: str = attrs.field(default="cover", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n + 1

    @produces.default
    def _produces(self) -> int:
        return self.n + 1

    def __str__(self) -> str:
        if self.n == 1:
            return self.teal_str("swap")
        else:
            return super().__str__()


@attrs.frozen
class Uncover(TealOpN):
    op_code: str = attrs.field(default="uncover", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n + 1

    @produces.default
    def _produces(self) -> int:
        return self.n + 1

    def __str__(self) -> str:
        if self.n == 1:
            return self.teal_str("swap")
        else:
            return super().__str__()


@attrs.frozen
class Dig(TealOpN):
    op_code: str = attrs.field(default="dig", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n + 1

    @produces.default
    def _produces(self) -> int:
        return self.n + 2


@attrs.frozen
class Bury(TealOpN):
    op_code: str = attrs.field(default="bury", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n

    @produces.default
    def _produces(self) -> int:
        return self.n - 1


@attrs.frozen
class FrameDig(TealOpN):
    op_code: str = attrs.field(default="frame_dig", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)


@attrs.frozen
class FrameBury(TealOpN):
    op_code: str = attrs.field(default="frame_bury", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)


@attrs.frozen
class PushInt(TealOp):
    n: int | str
    op_code: str = attrs.field(default="int", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.n,)


@attrs.frozen
class PopN(TealOpN):
    op_code: str = attrs.field(default="popn", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(default=0, init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n


@attrs.frozen
class DupN(TealOpN):
    op_code: str = attrs.field(default="dupn", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(init=False)

    @produces.default
    def _produces(self) -> int:
        return self.n + 1


@attrs.frozen
class Proto(TealOp):
    parameters: int
    returns: int
    op_code: str = attrs.field(default="proto", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return self.parameters, self.returns


@attrs.frozen
class PushBytes(TealOp):
    n: bytes
    encoding: AVMBytesEncoding
    op_code: str = attrs.field(default="byte", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

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
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.a,)


@attrs.frozen
class PushMethod(TealOp):
    a: str
    op_code: str = attrs.field(default="method", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

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


@attrs.define
class TealBlock:
    label: str
    ops: list[TealOp]
    entry_stack_height: int
    exit_stack_height: int

    def validate_stack_height(self) -> None:
        stack_height = self.entry_stack_height
        for op in self.ops:
            stack_height -= op.consumes
            if stack_height < 0:
                raise InternalError("Access below stack height", op.source_location)
            stack_height += op.produces
        expected_exit_height = self.exit_stack_height
        if stack_height != expected_exit_height and not (
            self.ops and self.ops[-1].op_code in ("return", "retsub", "err")
        ):
            raise InternalError(
                f"Stack size at block {self.label} exit is {stack_height},"
                f" expected {expected_exit_height}",
                self.ops[-1].source_location,
            )


@attrs.define
class TealSubroutine:
    signature: str
    blocks: list[TealBlock] = attrs.field(factory=list)


@attrs.define
class TealProgram:
    target_avm_version: int
    main: TealSubroutine
    subroutines: list[TealSubroutine]

    @property
    def all_subroutines(self) -> Iterable[TealSubroutine]:
        yield self.main
        yield from self.subroutines
