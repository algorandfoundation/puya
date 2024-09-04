import typing
from collections.abc import Iterable, Sequence

import attrs

from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.utils import format_bytes
from puya.mir.models import Signature
from puya.parse import SourceLocation


@attrs.frozen
class StackManipulation:
    manipulation: typing.Literal["insert", "pop", "define"]
    stack: typing.Literal["f", "x", "l"]
    local_id: str
    index: int
    defined: bool = True

    def __str__(self) -> str:
        if self.manipulation == "insert":
            return f"{self.stack}.insert({self.index}, {self.local_id!r})"
        elif self.manipulation == "pop":
            return f"{self.stack}.pop({self.index}) == {self.local_id!r}"
        else:
            return f"{self.stack}.define({self.local_id!r}, {self.defined})"


@attrs.frozen(kw_only=True)
class TealOp:
    op_code: str
    consumes: int
    produces: int
    source_location: SourceLocation | None = attrs.field(eq=False)
    comment: str | None = None
    """A comment that is always emitted, should only be used for user comments related to an
    op such as assert or err"""
    stack_manipulations: Sequence[StackManipulation] = attrs.field(
        default=(),
        converter=tuple[StackManipulation, ...],
        eq=False,
    )

    @property
    def immediates(self) -> Sequence[int | str]:
        return ()

    def teal(self) -> str:
        return self._teal_str(self.op_code, *self.immediates)

    def _teal_str(self, op_code: str, *immediates: int | str) -> str:
        teal_args = [op_code, *map(str, immediates)]
        if self.comment:
            comment = "\n//".join(self.comment.splitlines())
            teal_args.append(f"// {comment}")
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


@attrs.frozen
class Swap(TealOp):
    op_code: str = attrs.field(default="swap", init=False)
    consumes: int = 2
    produces: int = 2


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
class Int(TealOp):
    value: int | str
    op_code: str = attrs.field(default="int", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.value,)


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
class Byte(TealOp):
    value: bytes
    encoding: AVMBytesEncoding
    op_code: str = attrs.field(default="byte", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        # not all encodings can handle an empty bytes, so use base16 if bytes is empty
        encoding = self.encoding
        if not self.value and encoding in (AVMBytesEncoding.base32, AVMBytesEncoding.base64):
            encoding = AVMBytesEncoding.base16
        bytes_str = format_bytes(self.value, encoding)
        if encoding in (
            AVMBytesEncoding.utf8,
            AVMBytesEncoding.base16,
            AVMBytesEncoding.unknown,
        ):
            return (bytes_str,)
        hint = encoding.name
        return hint, bytes_str


@attrs.frozen
class TemplateVar(TealOp):
    name: str
    op_code: str
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.name,)


@attrs.frozen
class Address(TealOp):
    value: str
    op_code: str = attrs.field(default="addr", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.value,)


@attrs.frozen
class Method(TealOp):
    value: str
    op_code: str = attrs.field(default="method", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (f'"{self.value}"',)


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
    x_stack: Sequence[str]
    entry_stack_height: int
    exit_stack_height: int

    def validate(self) -> None:
        self._validate_stack_height()
        self._validate_stack_manipulations()

    def _validate_stack_height(self) -> None:
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

    def _validate_stack_manipulations(self) -> None:
        x_stack = list(self.x_stack)
        l_stack = list[str]()
        for op in self.ops:
            for sm in op.stack_manipulations:
                if sm.stack == "l":
                    stack = l_stack
                elif sm.stack == "x":
                    stack = x_stack
                else:
                    continue
                if sm.manipulation == "insert":
                    try:
                        stack.insert(sm.index, sm.local_id)
                    except ValueError:
                        stack_desc = ",".join(stack)
                        raise InternalError(f"invalid index {sm.index} for {stack_desc}") from None
                elif sm.manipulation == "pop":
                    try:
                        stack.pop(sm.index)
                    except IndexError:
                        stack_desc = ",".join(stack)
                        raise InternalError(
                            f"could not find {sm.local_id!r} in {sm.stack!r} stack: {stack_desc}"
                        ) from None
                # TODO: check define too?


@attrs.define
class TealSubroutine:
    is_main: bool
    signature: Signature
    blocks: list[TealBlock] = attrs.field(factory=list)


@attrs.define
class TealProgram:
    id: str
    target_avm_version: int
    main: TealSubroutine
    subroutines: list[TealSubroutine]

    @property
    def all_subroutines(self) -> Iterable[TealSubroutine]:
        yield self.main
        yield from self.subroutines
