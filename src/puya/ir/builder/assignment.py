from collections.abc import Sequence

import structlog

from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, TodoError
from puya.ir.avm_ops import AVMOp
from puya.ir.builder import arc4
from puya.ir.builder.utils import (
    assign,
)
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
from puya.parse import SourceLocation

logger = structlog.get_logger(__name__)


def handle_assignment_expr(
    context: IRFunctionBuildContext,
    target: awst_nodes.Expression,
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
) -> Sequence[Value]:
    match target:
        case awst_nodes.VarExpression(name=var_name, source_location=var_loc):
            return assign(
                context,
                source=value,
                names=[(var_name, var_loc)],
                source_location=assignment_location,
            )
        case awst_nodes.TemporaryVariable(source_location=var_loc) as tmp:
            tmp_name = context.get_awst_tmp_name(tmp)
            return assign(
                context,
                source=value,
                names=[(tmp_name, var_loc)],
                source_location=assignment_location,
            )
        case awst_nodes.TupleExpression(items=items):
            source = context.visitor.materialise_value_provider(
                value, description="tuple_assignment"
            )
            if len(source) != len(items):
                raise CodeError("unpacking vs result length mismatch", assignment_location)
            return [
                val
                for dst, src in zip(items, source, strict=True)
                for val in handle_assignment(
                    context,
                    target=dst,
                    value=src,
                    assignment_location=assignment_location,
                )
            ]
        case awst_nodes.AppStateExpression(
            key=app_state_key, source_location=key_loc, key_encoding=key_encoding
        ):
            source = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            if len(source) != 1:
                raise CodeError("Tuple state is not supported", assignment_location)
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_global_put,
                    args=[
                        BytesConstant(
                            value=app_state_key,
                            source_location=key_loc,
                            encoding=bytes_enc_to_avm_bytes_enc(key_encoding),
                        ),
                        source[0],
                    ],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.AppAccountStateExpression(
            key=app_acct_state_key,
            account=account_expr,
            source_location=key_loc,
            key_encoding=key_encoding,
        ):
            source = context.visitor.materialise_value_provider(
                value, description="new_state_value"
            )
            account = context.visitor.visit_and_materialise_single(account_expr)
            if len(source) != 1:
                raise CodeError("Tuple state is not supported", assignment_location)
            context.block_builder.add(
                Intrinsic(
                    op=AVMOp.app_local_put,
                    args=[
                        account,
                        BytesConstant(
                            value=app_acct_state_key,
                            source_location=key_loc,
                            encoding=bytes_enc_to_avm_bytes_enc(key_encoding),
                        ),
                        source[0],
                    ],
                    source_location=assignment_location,
                )
            )
            return source
        case awst_nodes.IndexExpression(
            base=awst_nodes.Expression(
                wtype=wtypes.ARC4DynamicArray() | wtypes.ARC4StaticArray() | wtypes.ARC4Struct()
            )
        ) as ix_expr:
            return (
                arc4.handle_arc4_assign(
                    context,
                    target=ix_expr,
                    value=value,
                    source_location=assignment_location,
                ),
            )
        case _:
            raise TodoError(
                assignment_location,
                "TODO: explicitly handle or reject assignment target type:"
                f" {type(target).__name__}",
            )
