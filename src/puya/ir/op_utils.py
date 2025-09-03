import typing
from collections.abc import Sequence

import attrs

from puya.avm import AVMType
from puya.ir.avm_ops import AVMOp
from puya.ir.models import (
    BytesConstant,
    Intrinsic,
    MultiValue,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import AVMBytesEncoding, IRType, PrimitiveIRType, SizedBytesType
from puya.parse import SourceLocation


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
    target: str,
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
    target_reg = mktemp(context, intrinsic.types[0], source_location, description=target)
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


@attrs.frozen
class OpFactory:
    context: IRRegisterContext
    source_location: SourceLocation | None

    def add(self, a: Value | int, b: Value | int, temp_desc: str = "add") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.add,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def sub(
        self, a: Value, b: Value | int, temp_desc: str = "sub", *, error_message: str | None = None
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.sub,
            args=[a, b],
            error_message=error_message,
            source_location=self.source_location,
        )
        return result

    def mul(self, a: Value | int, b: Value | int, temp_desc: str = "mul") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.mul,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def div_floor(self, a: Value | int, b: Value | int, temp_desc: str = "div_floor") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.div_floor,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def mod(self, a: Value | int, b: Value | int, temp_desc: str = "mod") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.mod,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def len(self, value: Value, temp_desc: str = "len") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.len_,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def bitlen(self, value: Value, temp_desc: str = "bitlen") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.bitlen,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def btoi(self, value: Value, temp_desc: str = "btoi") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.btoi,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def eq(
        self, a: Value | int | bytes, b: Value | int | bytes, temp_desc: str = "eq"
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.eq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def neq(
        self, a: Value | int | bytes, b: Value | int | bytes, temp_desc: str = "neq"
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.neq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def lt(self, a: Value | int, b: Value | int, temp_desc: str = "lt") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.lt,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def lte(self, a: Value | int, b: Value | int, temp_desc: str = "lte") -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.lte,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def neq_bytes(
        self, a: Value | bytes, b: Value | bytes, temp_desc: str = "neq_bytes"
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.neq_bytes,
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
        temp_desc: str = "select",
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

    def extract_uint16(
        self, a: Value, b: Value | int, temp_desc: str = "extract_uint16"
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint16,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def extract_uint64(
        self, a: Value, b: Value | int, temp_desc: str = "extract_uint64"
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract_uint64,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def itob(self, value: Value | int, temp_desc: str = "itob") -> Register:
        itob = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.itob,
            args=[value],
            source_location=self.source_location,
        )
        return itob

    def to_fixed_size(
        self,
        value: Value,
        *,
        num_bytes: int,
        temp_desc: str = "to_fixed_size",
        error_message: str | None = None,
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

    def pad_bytes(self, value: Value, *, num_bytes: int, temp_desc: str = "pad_bytes") -> Register:
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

    def as_u16_bytes(self, a: Value | int, temp_desc: str = "as_u16_bytes") -> Register:
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
        temp_desc: str = "concat",
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
        self,
        *,
        value: Value | bytes,
        index: Value | int,
        bit: Value | int,
        temp_desc: str = "set_bit",
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

    def get_bit(
        self,
        value: Value,
        index: Value | int,
        temp_desc: str = "get_bit",
        ir_type: IRType | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.getbit,
            args=[value, index],
            return_type=ir_type,
            source_location=self.source_location,
        )
        return result

    def arc4_false(self) -> Value:
        arc4_false = (0).to_bytes(1, "big")
        return self.constant(arc4_false)

    def make_arc4_bool(self, value: Value, temp_desc: str = "encoded_bool") -> Value:
        # TODO: compare with select implementation
        false = self.arc4_false()
        return self.set_bit(value=false, index=0, bit=value, temp_desc=temp_desc)

    def extract_to_end(
        self,
        value: Value,
        start: int | Value,
        temp_desc: str = "extract_to_end",
    ) -> Register:
        total_length = self.len(value, "total_length")
        return self.substring3(value, start, total_length, temp_desc)

    def substring3(
        self,
        value: Value | bytes,
        start: Value | int,
        end_ex: Value | int,
        temp_desc: str = "substring3",
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
        temp_desc: str = "replace",
        error_message: str | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            source_location=self.source_location,
            op=AVMOp.replace3,
            args=[value, index, replacement],
            error_message=error_message,
        )
        return result

    def extract3(
        self,
        value: Value | bytes,
        index: Value | int,
        length: Value | int,
        temp_desc: str = "extract",
        error_message: str | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract3,
            args=[value, index, length],
            source_location=self.source_location,
            error_message=error_message,
        )
        return result

    def box_extract(
        self,
        box_key: Value | bytes,
        offset: Value | int,
        length: Value | int,
        ir_type: IRType,
        temp_desc: str = "box_extract",
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.box_extract,
            args=[box_key, offset, length],
            return_type=ir_type,
            source_location=self.source_location,
        )
        return result

    def box_extract_u16(
        self,
        box_key: Value | bytes,
        offset: Value | int,
    ) -> Register:
        u16_bytes = self.box_extract(box_key, offset, 2, PrimitiveIRType.bytes)
        return self.btoi(u16_bytes)

    def box_replace(
        self, box_key: Value | bytes, offset: Value | int, value: Value | bytes
    ) -> Intrinsic:
        args = [box_key, offset, value]
        return Intrinsic(
            op=AVMOp.box_replace,
            args=[convert_constants(a, self.source_location) for a in args],
            source_location=self.source_location,
        )

    def assert_value(self, value: Value, *, error_message: str) -> None:
        assert_value(
            self.context, value, error_message=error_message, source_location=self.source_location
        )

    def materialise_single(self, value_provider: ValueProvider, description: str = "tmp") -> Value:
        (single,) = self.materialise_values(value_provider, description)
        return single

    def materialise_values(
        self, value_provider: ValueProvider, description: str = "tmp"
    ) -> Sequence[Value]:
        return self.context.materialise_value_provider(value_provider, description)

    def as_ir_type(self, value: ValueProvider, ir_type: IRType) -> Value:
        (value_ir_type,) = value.types
        if value_ir_type == ir_type:
            return self.materialise_single(value)
        else:
            target = mktemp(
                self.context, ir_type, self.source_location, description=f"as_{ir_type!s}"
            )
            assign_targets(
                self.context,
                source=value,
                targets=[target],
                assignment_location=self.source_location,
            )
            return target

    def materialise_multi_value(self, result: ValueProvider) -> MultiValue:
        if isinstance(result, MultiValue):
            return result
        else:
            values = self.materialise_values(result)
            if len(values) == 1:
                return values[0]
            else:
                return ValueTuple(values=values, source_location=self.source_location)
