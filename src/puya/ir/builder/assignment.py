import typing
from collections.abc import Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder._utils import assign
from puya.ir.builder.box import handle_box_assign
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    BytesConstant,
    Intrinsic,
    Value,
    ValueProvider,
)
from puya.ir.types_ import (
    bytes_enc_to_avm_bytes_enc,
)
from puya.ir.utils import lvalue_items
from puya.parse import SourceLocation

logger = log.get_logger(__name__)


def handle_assignment_expr(
    context: IRFunctionBuildContext,
    target: awst_nodes.Lvalue,
    value: awst_nodes.Expression,
    assignment_location: SourceLocation,
) -> Sequence[Value]:
    expr_values = context.visitor.visit_expr(value)
    return handle_assignment(
        context, target=target, value=expr_values, assignment_location=assignment_location
    )


def handle_assignment(
    context: IRFunctionBuildContext,
    target: awst_nodes.Lvalue,
    value: ValueProvider,
    assignment_location: SourceLocation,
    *,
    is_recursive_assign: bool = False,
) -> Sequence[Value]:
    match target:
        case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
            if (
                var_name in (p.name for p in context.subroutine.parameters if p.implicit_return)
                and not is_recursive_assign
            ):
                raise CodeError(
                    f"Cannot reassign mutable parameter {var_name!r}"
                    " which is being passed by reference",
                    assignment_location,
                )
            return assign(
                context,
                source=value,
                names=[(var_name, var_loc)],
                source_location=assignment_location,
            )
        case awst_nodes.TupleExpression() as tup_expr:
            source = context.visitor.materialise_value_provider(
                value, description="tuple_assignment"
            )
            items = lvalue_items(tup_expr)
            if len(source) != len(items):
                raise CodeError("unpacking vs result length mismatch", assignment_location)
            return [
                val
                for dst, src in zip(items, source, strict=True)
                for val in handle_assignment(
                    context, target=dst, value=src, assignment_location=assignment_location
                )
            ]
        case awst_nodes.AppStateExpression(field_name=field_name, source_location=key_loc):
            source = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            if len(source) != 1:
                raise CodeError("Tuple state is not supported", assignment_location)
            state_def = context.resolve_state(field_name, key_loc)
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_global_put,
                    args=[
                        BytesConstant(
                            value=state_def.key,
                            source_location=key_loc,
                            encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
                        ),
                        source[0],
                    ],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.AppAccountStateExpression(
            field_name=field_name,
            account=account_expr,
            source_location=key_loc,
        ):
            source = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            account = context.visitor.visit_and_materialise_single(account_expr)
            if len(source) != 1:
                raise CodeError("Tuple state is not supported", assignment_location)
            state_def = context.resolve_state(field_name, key_loc)
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_local_put,
                    args=[
                        account,
                        BytesConstant(
                            value=state_def.key,
                            source_location=key_loc,
                            encoding=bytes_enc_to_avm_bytes_enc(state_def.key_encoding),
                        ),
                        source[0],
                    ],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.IndexExpression() as ix_expr:
            if isinstance(ix_expr.base.wtype, wtypes.WArray):
                raise NotImplementedError
            elif isinstance(ix_expr.base.wtype, wtypes.ARC4Type):  # noqa: RET506
                return (
                    arc4.handle_arc4_assign(
                        context,
                        target=ix_expr,
                        value=value,
                        source_location=assignment_location,
                    ),
                )
            else:
                raise InternalError(
                    f"Indexed assignment operation IR lowering"
                    f" not implemented for base type {ix_expr.base.wtype.name}",
                    assignment_location,
                )
        case awst_nodes.FieldExpression() as field_expr:
            if isinstance(field_expr.base.wtype, wtypes.WStructType):
                raise NotImplementedError
            elif isinstance(field_expr.base.wtype, wtypes.ARC4Struct):  # noqa: RET506
                return (
                    arc4.handle_arc4_assign(
                        context,
                        target=field_expr,
                        value=value,
                        source_location=assignment_location,
                    ),
                )
            else:
                raise InternalError(
                    f"Field assignment operation IR lowering"
                    f" not implemented for base type {field_expr.base.wtype.name}",
                    assignment_location,
                )
        case awst_nodes.BoxValueExpression() as box:
            return handle_box_assign(
                context=context, box=box, value=value, assignment_location=assignment_location
            )

        case _:
            typing.assert_never(target)
