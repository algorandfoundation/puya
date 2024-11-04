import typing
from collections.abc import Sequence

import attrs

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.context import IRFunctionBuildContext, IRRegisterContext
from puya.ir.models import (
    TMP_VAR_INDICATOR,
    BytesConstant,
    Intrinsic,
    InvokeSubroutine,
    Register,
    UInt64Constant,
    Value,
    ValueProvider,
)
from puya.ir.types_ import AVMBytesEncoding, IRType, PrimitiveIRType
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


# TODO: move this into context?
def update_implicit_out_var(context: IRFunctionBuildContext, var: str, ir_type: IRType) -> None:
    # emit conditional assignment equivalent to
    # if var%is_original:
    #   var%out = var
    loc = SourceLocation(file=None, line=1)
    wtype = wtypes.bytes_wtype if ir_type == PrimitiveIRType.bytes else wtypes.uint64_wtype
    node = awst_nodes.IfElse(
        condition=awst_nodes.VarExpression(
            name=get_implicit_return_is_original(var),
            wtype=wtypes.bool_wtype,
            source_location=loc,
        ),
        if_branch=awst_nodes.Block(
            body=[
                awst_nodes.AssignmentStatement(
                    target=awst_nodes.VarExpression(
                        name=get_implicit_return_out(var),
                        wtype=wtype,
                        source_location=loc,
                    ),
                    value=awst_nodes.VarExpression(
                        name=var,
                        wtype=wtype,
                        source_location=loc,
                    ),
                    source_location=loc,
                )
            ],
            source_location=loc,
        ),
        else_branch=None,
        source_location=loc,
    )
    node.accept(context.visitor)


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
        args=[_convert_constants(a, source_location) for a in args],
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


def _convert_constants(arg: int | bytes | Value, source_location: SourceLocation | None) -> Value:
    match arg:
        case int(val):
            return UInt64Constant(value=val, source_location=source_location)
        case bytes(b_val):
            return BytesConstant(
                value=b_val, encoding=AVMBytesEncoding.unknown, source_location=source_location
            )
        case _:
            return arg


def invoke_puya_lib_subroutine(
    context: IRFunctionBuildContext,
    *,
    full_name: str,
    args: Sequence[Value | int | bytes],
    source_location: SourceLocation,
) -> InvokeSubroutine:
    sub = context.embedded_funcs_lookup[full_name]
    return InvokeSubroutine(
        target=sub,
        args=[_convert_constants(arg, source_location) for arg in args],
        source_location=source_location,
    )


def assert_value(
    context: IRRegisterContext, value: Value, *, source_location: SourceLocation, comment: str
) -> None:
    context.add_op(
        Intrinsic(
            op=AVMOp.assert_,
            source_location=source_location,
            args=[value],
            error_message=comment,
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

    def btoi(self, value: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.btoi,
            args=[value],
            source_location=self.source_location,
        )
        return result

    def eq(self, a: Value, b: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.eq,
            args=[a, b],
            source_location=self.source_location,
        )
        return result

    def select(self, false: Value, true: Value, condition: Value, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.select,
            args=[false, true, condition],
            return_type=true.ir_type,
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

    def itob(
        self, value: Value | int, temp_desc: str, return_type: IRType | None = None
    ) -> Register:
        itob = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.itob,
            args=[value],
            return_type=return_type,
            source_location=self.source_location,
        )
        return itob

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
        return_type: IRType | None = None,
        error_message: str | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.concat,
            args=[a, b],
            source_location=self.source_location,
            return_type=return_type,
            error_message=error_message,
        )
        return result

    def constant(self, value: int | bytes, ir_type: IRType | None = None) -> Value:
        if isinstance(value, int):
            return UInt64Constant(
                value=value,
                source_location=self.source_location,
                ir_type=ir_type or PrimitiveIRType.uint64,
            )
        else:
            return BytesConstant(
                value=value,
                encoding=AVMBytesEncoding.base16,
                ir_type=ir_type or PrimitiveIRType.bytes,
                source_location=self.source_location,
            )

    def set_bit(self, *, value: Value, index: int, bit: Value | int, temp_desc: str) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.setbit,
            args=[value, index, bit],
            return_type=value.ir_type,
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
        self, value: Value, start: int, temp_desc: str, *, return_type: IRType | None = None
    ) -> Register:
        if start > 255:
            raise InternalError(
                "Cannot use extract with a length of 0 if start > 255", self.source_location
            )
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract,
            immediates=[start, 0],
            args=[value],
            return_type=return_type,
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
            return_type=value.ir_type if isinstance(value, Value) else PrimitiveIRType.bytes,
        )
        return result

    def extract3(
        self,
        value: Value | bytes,
        index: Value | int,
        length: Value | int,
        temp_desc: str,
        return_type: IRType | None = None,
    ) -> Register:
        result = assign_intrinsic_op(
            self.context,
            target=temp_desc,
            op=AVMOp.extract3,
            args=[value, index, length],
            return_type=return_type,
            source_location=self.source_location,
        )
        return result
