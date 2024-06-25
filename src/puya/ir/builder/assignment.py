import typing
from collections.abc import Sequence

from puya import arc4_util, log
from puya.avm_type import AVMType
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder._utils import assign
from puya.ir.context import IRFunctionBuildContext
from puya.ir.models import (
    Intrinsic,
    Value,
    ValueProvider,
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
    target: awst_nodes.Expression,
    value: ValueProvider,
    assignment_location: SourceLocation,
    *,
    is_mutation: bool = False,
) -> Sequence[Value]:
    # separating out the target LValue check allows the _handle_assignment to statically assert
    # all LValue types are covered
    if not isinstance(target, awst_nodes.Lvalue):  # type: ignore[arg-type]
        raise CodeError("expression is not valid as an assignment target", target.source_location)
    return _handle_assignment(
        context,
        typing.cast(awst_nodes.Lvalue, target),
        value,
        assignment_location,
        is_mutation=is_mutation,
    )


def _handle_assignment(
    context: IRFunctionBuildContext,
    target: awst_nodes.Lvalue,
    value: ValueProvider,
    assignment_location: SourceLocation,
    *,
    is_mutation: bool,
) -> Sequence[Value]:
    match target:
        case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
            is_implicit_return = var_name in (
                p.name for p in context.subroutine.parameters if p.implicit_return
            )
            if is_implicit_return and not is_mutation:
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
        case awst_nodes.AppStateExpression(
            key=awst_key, wtype=wtype, source_location=field_location
        ):
            _ = wtypes.persistable_stack_type(wtype, field_location)  # double check
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            (mat_value, *rest) = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            assert not rest, "non-tuple state should have been already validated by AWST"
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_global_put,
                    args=[key_value, mat_value],
                    source_location=assignment_location,
                )
            )
            return [mat_value]
        case awst_nodes.AppAccountStateExpression(
            key=awst_key, account=account_expr, wtype=wtype, source_location=field_location
        ):
            _ = wtypes.persistable_stack_type(wtype, field_location)  # double check
            account = context.visitor.visit_and_materialise_single(account_expr)
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            (mat_value, *rest) = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            assert not rest, "non-tuple state should have been already validated by AWST"
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_local_put,
                    args=[account, key_value, mat_value],
                    source_location=assignment_location,
                )
            )
            return [mat_value]
        case awst_nodes.BoxValueExpression(
            key=awst_key, wtype=wtype, source_location=field_location
        ):
            scalar_type = wtypes.persistable_stack_type(wtype, field_location)  # double check
            key_value = context.visitor.visit_and_materialise_single(awst_key)
            (mat_value,) = context.visitor.materialise_value_provider(
                value, description="new_box_value"
            )
            if scalar_type == AVMType.bytes:
                serialized_value = mat_value
                if not (
                    isinstance(wtype, wtypes.ARC4Type) and arc4_util.is_arc4_static_size(wtype)
                ):
                    context.block_builder.add(
                        Intrinsic(
                            op=AVMOp.box_del, args=[key_value], source_location=assignment_location
                        )
                    )
            elif scalar_type == AVMType.uint64:
                (serialized_value,) = assign(
                    context=context,
                    temp_description="new_box_value",
                    source=Intrinsic(
                        op=AVMOp.itob,
                        args=[mat_value],
                        source_location=assignment_location,
                    ),
                    source_location=assignment_location,
                )
            else:
                typing.assert_never(scalar_type)
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.box_put,
                    args=[key_value, serialized_value],
                    source_location=assignment_location,
                )
            )
            return [mat_value]
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
        case _:
            typing.assert_never(target)
