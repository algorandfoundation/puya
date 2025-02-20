import abc
import typing
from collections.abc import Iterable, Mapping, Sequence

import attrs

from puya.avm import OnCompletionAction, TransactionType
from puya.errors import InternalError
from puya.ir.types_ import AVMBytesEncoding
from puya.ir.utils import format_bytes, format_error_comment
from puya.mir import models as mir
from puya.parse import SourceLocation
from puya.program_refs import ProgramKind
from puya.utils import valid_bytes, valid_int64

MAX_NUMBER_CONSTANTS = 256
TEAL_ALIASES = {
    **{e.name: e.value for e in OnCompletionAction},
    **{e.name: e.value for e in TransactionType},
}


@attrs.frozen
class StackConsume:
    n: int


@attrs.frozen
class StackExtend:
    local_ids: Sequence[str]


@attrs.frozen
class StackInsert:
    depth: int
    local_id: str


@attrs.frozen
class StackPop:
    depth: int


@attrs.frozen
class StackDefine:
    local_ids: Sequence[str]


StackManipulation = StackConsume | StackExtend | StackDefine | StackInsert | StackPop


@attrs.frozen(kw_only=True)
class TealOp:
    op_code: str
    consumes: int
    produces: int
    source_location: SourceLocation | None = attrs.field(eq=False)
    comment: str | None = None
    """A comment that is always emitted after the op in TEAL"""
    error_message: str | None = None
    """Error message to display if program fails at this op"""
    stack_manipulations: Sequence[StackManipulation] = attrs.field(
        default=(),
        converter=tuple[StackManipulation, ...],
        eq=False,
    )

    @property
    def immediates(self) -> Sequence[int | str]:
        return ()

    def teal(self) -> str:
        teal_args = [self.op_code, *map(str, self.immediates)]
        if self.comment or self.error_message:
            error_message = (
                format_error_comment(self.op_code, self.error_message)
                if self.error_message
                else ""
            )
            comment_lines = error_message.splitlines()
            comment_lines += (self.comment or "").splitlines()
            comment = "\n//".join(comment_lines)
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
class TealOpN(TealOp):
    n: int = attrs.field(validator=[attrs.validators.ge(0), attrs.validators.le(255)])

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.n,)


@attrs.frozen
class TealOpUInt8(TealOpN):
    n: int = attrs.field(validator=[attrs.validators.ge(0), attrs.validators.le(255)])


@attrs.frozen
class TealOpInt8(TealOpN):
    n: int = attrs.field(validator=[attrs.validators.ge(-128), attrs.validators.le(127)])


@attrs.frozen
class Cover(TealOpUInt8):
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
class Uncover(TealOpUInt8):
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
class Dig(TealOpUInt8):
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
class Bury(TealOpUInt8):
    op_code: str = attrs.field(default="bury", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n

    @produces.default
    def _produces(self) -> int:
        return self.n - 1


def _valid_uint64(node: TealOp, _attribute: object, value: int) -> None:
    if not valid_int64(value):
        raise InternalError(
            "Invalid UInt64 value",
            node.source_location,
        )


def _valid_bytes(node: TealOp, _attribute: object, value: bytes) -> None:
    if not valid_bytes(value):
        raise InternalError("Invalid Bytes value", node.source_location)


def _valid_ref(node: TealOp, _attribute: object, value: int) -> None:
    if value < 0 or value >= MAX_NUMBER_CONSTANTS:
        raise InternalError(
            "Invalid constant reference",
            node.source_location,
        )


@attrs.frozen
class IntBlock(TealOp):
    op_code: str = attrs.field(default="intcblock", init=False)
    constants: Mapping[int | str, SourceLocation | None]
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return tuple(self.constants)


@attrs.frozen
class IntC(TealOp):
    index: int = attrs.field(validator=_valid_ref)
    op_code: str = attrs.field(init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @op_code.default
    def _op_code(self) -> str:
        if self.index < 4:
            return f"intc_{self.index}"
        else:
            return "intc"

    @property
    def immediates(self) -> Sequence[int]:
        if self.index < 4:
            return ()
        else:
            return (self.index,)


@attrs.frozen
class PushInt(TealOp):
    op_code: str = attrs.field(default="pushint", init=False)
    value: int = attrs.field(validator=_valid_uint64)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int]:
        return (self.value,)


@attrs.frozen
class PushInts(TealOp):
    op_code: str = attrs.field(default="pushints", init=False)
    values: list[int] = attrs.field(validator=attrs.validators.deep_iterable(_valid_uint64))
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(init=False)

    @produces.default
    def _produces(self) -> int:
        return len(self.values)

    @property
    def immediates(self) -> Sequence[int]:
        return self.values


@attrs.frozen
class BytesBlock(TealOp):
    op_code: str = attrs.field(default="bytecblock", init=False)
    constants: Mapping[bytes | str, tuple[AVMBytesEncoding, SourceLocation | None]]
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[str]:
        return tuple(
            _encoded_bytes(c, es[0]) if isinstance(c, bytes) else c
            for c, es in self.constants.items()
        )


@attrs.frozen
class BytesC(TealOp):
    index: int = attrs.field(validator=_valid_ref)
    op_code: str = attrs.field(init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @op_code.default
    def _op_code(self) -> str:
        if self.index < 4:
            return f"bytec_{self.index}"
        else:
            return "bytec"

    @property
    def immediates(self) -> Sequence[int]:
        if self.index < 4:
            return ()
        else:
            return (self.index,)


@attrs.frozen
class PushBytes(TealOp):
    op_code: str = attrs.field(default="pushbytes", init=False)
    value: bytes = attrs.field(validator=_valid_bytes)
    # exclude encoding from equality so for example 0x and "" can be combined
    encoding: AVMBytesEncoding = attrs.field(eq=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[str]:
        return (_encoded_bytes(self.value, self.encoding),)


@attrs.frozen
class PushBytess(TealOp):
    op_code: str = attrs.field(default="pushbytess", init=False)
    values: Sequence[tuple[bytes, AVMBytesEncoding]] = attrs.field()
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(init=False)

    @produces.default
    def _produces(self) -> int:
        return len(self.values)

    @values.validator
    def _values_validator(
        self, _: object, value: Sequence[tuple[bytes, AVMBytesEncoding]]
    ) -> None:
        if not all(valid_bytes(b) for b, _ in value):
            raise InternalError("invalid bytes value", self.source_location)

    @property
    def immediates(self) -> Sequence[str]:
        return tuple(_encoded_bytes(c, e) for c, e in self.values)


@attrs.frozen
class FrameDig(TealOpInt8):
    op_code: str = attrs.field(default="frame_dig", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)


@attrs.frozen
class FrameBury(TealOpInt8):
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
class PopN(TealOpUInt8):
    op_code: str = attrs.field(default="popn", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(default=0, init=False)

    @consumes.default
    def _consumes(self) -> int:
        return self.n


@attrs.frozen
class DupN(TealOpUInt8):
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
    # exclude encoding from equality so for example 0x and "" can be combined
    encoding: AVMBytesEncoding = attrs.field(eq=False)
    op_code: str = attrs.field(default="byte", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=1, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (_encoded_bytes(self.value, self.encoding),)


@attrs.frozen
class TemplateVar(TealOp):
    name: str
    op_code: typing.Literal["int", "byte"]
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
class ControlOp(TealOp, abc.ABC):
    @property
    @abc.abstractmethod
    def targets(self) -> Sequence[str]: ...


@attrs.frozen
class RetSub(ControlOp):
    op_code: str = attrs.field(default="retsub", init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def targets(self) -> Sequence[str]:
        return ()


@attrs.frozen
class Return(ControlOp):
    op_code: str = attrs.field(default="return", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def targets(self) -> Sequence[str]:
        return ()


@attrs.frozen
class Err(ControlOp):
    op_code: str = attrs.field(default="err", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def targets(self) -> Sequence[str]:
        return ()


@attrs.frozen
class Branch(ControlOp):
    target: str
    op_code: str = attrs.field(default="b", init=False)
    consumes: int = attrs.field(default=0, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.target,)

    @property
    def targets(self) -> Sequence[str]:
        return (self.target,)


@attrs.frozen
class BranchNonZero(ControlOp):
    target: str
    op_code: str = attrs.field(default="bnz", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.target,)

    @property
    def targets(self) -> Sequence[str]:
        return (self.target,)


@attrs.frozen
class BranchZero(ControlOp):
    target: str
    op_code: str = attrs.field(default="bz", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.target,)

    @property
    def targets(self) -> Sequence[str]:
        return (self.target,)


@attrs.frozen
class Switch(ControlOp):
    targets: Sequence[str] = attrs.field(converter=tuple[str, ...])
    op_code: str = attrs.field(default="switch", init=False)
    consumes: int = attrs.field(default=1, init=False)
    produces: int = attrs.field(default=0, init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return self.targets


@attrs.frozen
class Match(ControlOp):
    targets: Sequence[str] = attrs.field(converter=tuple[str, ...])
    op_code: str = attrs.field(default="match", init=False)
    consumes: int = attrs.field(init=False)
    produces: int = attrs.field(default=0, init=False)

    @consumes.default
    def _consumes(self) -> int:
        return len(self.targets) + 1

    @property
    def immediates(self) -> Sequence[int | str]:
        return self.targets


@attrs.frozen
class CallSub(TealOp):
    target: str
    op_code: str = attrs.field(default="callsub", init=False)

    @property
    def immediates(self) -> Sequence[int | str]:
        return (self.target,)


@attrs.frozen
class TealBlock:
    label: str
    ops: list[TealOp]
    x_stack_in: Sequence[str]
    entry_stack_height: int = attrs.field(validator=attrs.validators.ge(0))
    exit_stack_height: int = attrs.field(validator=attrs.validators.ge(0))

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


@attrs.frozen
class TealSubroutine:
    is_main: bool
    signature: mir.Signature
    blocks: list[TealBlock]
    source_location: SourceLocation | None


@attrs.define
class TealProgram:
    kind: ProgramKind
    avm_version: int
    main: TealSubroutine
    subroutines: list[TealSubroutine]

    @property
    def all_subroutines(self) -> Iterable[TealSubroutine]:
        yield self.main
        yield from self.subroutines


def _encoded_bytes(value: bytes, encoding: AVMBytesEncoding) -> str:
    # not all encodings can handle an empty bytes, so use base16 if bytes is empty
    if not value and encoding in (AVMBytesEncoding.base32, AVMBytesEncoding.base64):
        encoding = AVMBytesEncoding.base16
    bytes_str = format_bytes(value, encoding)
    if encoding in (
        AVMBytesEncoding.utf8,
        AVMBytesEncoding.base16,
        AVMBytesEncoding.unknown,
    ):
        return bytes_str
    hint = encoding.name
    return f"{hint}({bytes_str})"
