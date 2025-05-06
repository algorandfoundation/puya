import typing
from collections.abc import Sequence

import attrs

from puya.avm import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.models import (
    TMP_VAR_INDICATOR,
    BytesConstant,
    Intrinsic,
    Register,
    UInt64Constant,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import (
    AVMBytesEncoding,
    IRType,
    PrimitiveIRType,
    SizedBytesType,
    wtype_to_ir_types,
)
from puya.parse import SourceLocation


def assign(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    name: str,
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> Register:
    (ir_type,) = source.types
    target = context.new_register(name, ir_type, register_location or assignment_location)
    assign_targets(
        context=context,
        source=source,
        targets=[target],
        assignment_location=assignment_location,
    )
    return target


def new_register_version(context: IRRegisterContext, reg: Register) -> Register:
    return context.new_register(name=reg.name, ir_type=reg.ir_type, location=reg.source_location)


def assign_temp(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    temp_description: str,
    source_location: SourceLocation | None,
) -> Register:
    (ir_type,) = source.types
    target = mktemp(context, ir_type, source_location, description=temp_description)
    assign_targets(
        context,
        source=source,
        targets=[target],
        assignment_location=source_location,
    )
    return target


def assign_targets(
    context: IRRegisterContext,
    *,
    source: ValueProvider,
    targets: list[Register],
    assignment_location: SourceLocation | None,
) -> None:
    if not (source.types or targets):
        return
    context.add_assignment(targets, source, assignment_location)


def get_implicit_return_is_original(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}is_original"


def get_implicit_return_out(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}out"


def mktemp(
    context: IRRegisterContext,
    ir_type: IRType,
    source_location: SourceLocation | None,
    *,
    description: str,
) -> Register:
    name = context.next_tmp_name(description)
    return context.new_register(name, ir_type, source_location)


def assign_intrinsic_op(
    context: IRRegisterContext,
    *,
    target: str | Register,
    op: AVMOp,
    args: Sequence[int | bytes | Value],
    source_location: SourceLocation | None,
    immediates: list[int | str] | None = None,
    return_type: IRType | None = None,
    error_message: str | None = None,
) -> Register:
    intrinsic = Intrinsic(
        op=op,
        immediates=immediates or [],
        args=[convert_constants(a, source_location) for a in args],
        types=(
            [return_type]
            if return_type is not None
            else typing.cast(Sequence[IRType], attrs.NOTHING)
        ),
        error_message=error_message,
        source_location=source_location,
    )
    if isinstance(target, str):
        target_reg = mktemp(context, intrinsic.types[0], source_location, description=target)
    else:
        target_reg = new_register_version(context, target)
    assign_targets(
        context,
        targets=[target_reg],
        source=intrinsic,
        assignment_location=source_location,
    )
    return target_reg


def convert_constants(arg: int | bytes | Value, source_location: SourceLocation | None) -> Value:
    match arg:
        case int(val):
            return UInt64Constant(value=val, source_location=source_location)
        case bytes(b_val):
            return BytesConstant(
                value=b_val, encoding=AVMBytesEncoding.unknown, source_location=source_location
            )
        case _:
            return arg


def assert_value(
    context: IRRegisterContext,
    value: Value,
    *,
    error_message: str,
    source_location: SourceLocation | None,
) -> None:
    context.add_op(
        Intrinsic(
            op=AVMOp.assert_,
            args=[value],
            error_message=error_message,
            source_location=source_location,
        )
    )


def extract_const_int(expr: awst_nodes.Expression | int | None) -> int | None:
    """
    Check expr is an IntegerConstant, int literal, or None, and return constant value (or None)
    """
    match expr:
        case None:
            return None
        case awst_nodes.IntegerConstant(value=value):
            return value
        case int(value):
            return value
        case _:
            raise InternalError(
                f"Expected either constant or None for index, got {type(expr).__name__}",
                expr.source_location,
            )


@attrs.frozen
class OpFactory:
    context: IRRegisterContext
    source_location: SourceLocation | None

    def assign(self, value: ValueProvider, temp_desc: str) -> Register:
        register = assign_temp(
            self.context, value, temp_description=temp_desc, source_location=self.source_location
        )
        return register

    def assign_multiple(self, **values: ValueProvider) -> Sequence[Register]:
        return [self.assign(value, desc) for desc, value in values.items()]

    def add(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.add,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def sub(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.sub,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def mul(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.mul,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def div_floor(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.div_floor,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def len(self, value: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.len_,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def bitlen(self, value: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.bitlen,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def btoi(self, value: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.btoi,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def eq(self, a: Value | int, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.eq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def lte(self, a: Value | int, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.lte,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def select(
        self,
        *,
        false: Value | int | bytes,
        true: Value | int | bytes,
        condition: Value,
        temp_desc: str,
        ir_type: IRType,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.select,
            args=[false, true, condition],
            return_type=ir_type,
            source_location=self.source_location,
        )
        return result

    def extract_uint8(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.getbyte,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def extract_uint16(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint16,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def extract_uint64(self, a: Value, b: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint64,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def itob(self, value: Value | int, temp_desc: str) -> Register:
        itob = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.itob,
            args=[value],
            source_location=self.source_location,
        )
        return itob

    def to_fixed_size(
        self, value: Value, *, num_bytes: int, temp_desc: str, error_message: str | None = None
    ) -> Register:
        assert value.atype == AVMType.bytes, "function expects a bytes-backed value to convert"
        # note this excludes values that are valid when interpreted as big-endian values but may
        # exceed the bytes size due to leading zero bytes, however it would be less efficient to
        # do both a pad and truncate to support that case
        value_len = self.len(value, "value_len")
        len_ok = self.lte(value_len, num_bytes, "len_ok")
        assert_value(
            self.context,
            len_ok,
            error_message=error_message or f"value is bigger than {num_bytes} bytes",
            source_location=self.source_location,
        )
        return self._unsafe_pad_bytes(value, num_bytes=num_bytes, temp_desc=temp_desc)

    def pad_bytes(self, value: Value, *, num_bytes: int, temp_desc: str) -> Register:
        assert isinstance(value.ir_type, SizedBytesType) and value.ir_type.num_bytes <= num_bytes
        return self._unsafe_pad_bytes(value, num_bytes=num_bytes, temp_desc=temp_desc)

    def _unsafe_pad_bytes(self, value: Value, *, num_bytes: int, temp_desc: str) -> Register:
        # it's unsafe because we type the result as SizedBytesType, which might not be the case
        # if the value is larger than num_bytes already
        zero = assign_intrinsic_op(
            self.context,
            target="bzero",
            op=AVMOp.bzero,
            args=[num_bytes],
            source_location=self.source_location,
        )
        return assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.bitwise_or_bytes,
            args=[value, zero],
            return_type=SizedBytesType(num_bytes=num_bytes),
            source_location=self.source_location,
        )

    def as_u16_bytes(self, a: Value | int, temp_desc: str) -> Register:
        as_bytes = self.itob(a, "as_bytes")
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract,
            immediates=[6, 2],
            args=[as_bytes],
            source_location=self.source_location,
        )
        return result

    def concat(
        self,
        a: Value | bytes,
        b: Value | bytes,
        temp_desc: str,
        *,
        ir_type: IRType | None = None,
        error_message: str | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.concat,
            args=[a, b],
            return_type=ir_type,
            source_location=self.source_location,
            error_message=error_message,
        )
        return result

    def constant(self, value: int | bytes, *, ir_type: IRType | None = None) -> Value:
        if isinstance(value, int):
            return UInt64Constant(
                value=value,
                ir_type=ir_type or attrs.NOTHING,  # type: ignore[arg-type]
                source_location=self.source_location,
            )
        else:
            return BytesConstant(
                value=value,
                ir_type=ir_type or attrs.NOTHING,  # type: ignore[arg-type]
                encoding=AVMBytesEncoding.base16,
                source_location=self.source_location,
            )

    def set_bit(
        self, *, value: Value | bytes, index: Value | int, bit: Value | int, temp_desc: str
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.setbit,
            args=[value, index, bit],
            return_type=value.ir_type if isinstance(value, Value) else PrimitiveIRType.bytes,
            source_location=self.source_location,
        )
        return result

    def get_bit(self, value: Value, index: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.getbit,
            args=[value, index],
            source_location=self.source_location,
        )
        return result

    def extract_to_end(
        self, value: Value, start: int | Value, temp_desc: str, *, ir_type: IRType | None = None
    ) -> Register:
        if isinstance(start, int) and start <= 255:
            pass
        elif isinstance(start, UInt64Constant) and start.value <= 255:
            start = start.value
        else:
            total_length = self.len(value, "total_length")
            return self.substring3(value, start, total_length, "data")
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract,
            immediates=[start, 0],
            args=[value],
            return_type=ir_type,
            source_location=self.source_location,
        )
        return result

    def substring3(
        self,
        value: Value | bytes,
        start: Value | int,
        end_ex: Value | int,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.substring3,
            args=[value, start, end_ex],
            source_location=self.source_location,
        )
        return result

    def replace(
        self,
        value: Value | bytes,
        index: Value | int,
        replacement: Value | bytes,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            source_location=self.source_location,
            op=AVMOp.replace3,
            args=[value, index, replacement],
        )
        return result

    def extract3(
        self,
        value: Value | bytes,
        index: Value | int,
        length: Value | int,
        temp_desc: str,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract3,
            args=[value, index, length],
            source_location=self.source_location,
        )
        return result


def undefined_value(typ: wtypes.WType, loc: SourceLocation) -> ValueProvider:
    """For a given WType, produce an "undefined" ValueProvider of the correct arity.

    It is invalid to request an "undefined" value of type void
    """
    values = [
        Undefined(ir_type=ir_type, source_location=loc) for ir_type in wtype_to_ir_types(typ, loc)
    ]
    match values:
        case []:
            raise InternalError("unexpected void type", loc)
        case [value]:
            return value
        case _:
            return ValueTuple(values=values, source_location=loc)
