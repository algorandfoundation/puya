import typing
from collections.abc import Iterable, Sequence

import attrs

from puya import log
from puya.errors import CodeError, InternalError
from puya.models import OnCompletionAction, TransactionType
from puya.parse import SourceLocation
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import Event
from puya.ussemble.desc_visitor import OpDescription

logger = log.get_logger(__name__)

TEAL_ALIASES = {
    **{e.name: e.value for e in OnCompletionAction},
    **{e.name: e.value for e in TransactionType},
}


def lower_ops(ctx: AssembleContext, program: teal.TealProgram) -> list[models.Node]:
    avm_ops = list[models.Node]()
    events = ctx.events
    function_block_ids = {s.blocks[0].label: s.signature.name for s in program.all_subroutines}

    def update_event(**params: typing.Any) -> None:
        op_index = len(avm_ops)
        event = events.get(op_index, Event())
        events[op_index] = attrs.evolve(
            event,
            **params,
        )

    for subroutine in program.all_subroutines:
        update_event(
            subroutine=subroutine.signature.name,
            params={p.local_id: p.atype.name or "" for p in subroutine.signature.parameters},
        )
        stack = list[str]()
        for block in subroutine.blocks:
            # stack = stack[: block.entry_stack_height - len(block.x_stack_in)]
            # stack.extend(block.x_stack_in)
            # update stack with correct values on entry to a block
            f_stack_height = block.entry_stack_height - len(block.x_stack_in)
            stack[f_stack_height:] = block.x_stack_in
            update_event(
                block=block.label,
                stack_in=stack.copy(),
            )
            avm_ops.append(models.Label(name=block.label))
            for op in block.ops:
                stack_modified = False
                defined = list[str]()
                for sm in op.stack_manipulations:
                    match sm:
                        case teal.StackConsume(n=n):
                            for _ in range(n):
                                stack.pop()
                            stack_modified = True
                        case teal.StackExtend() as se:
                            stack.extend(se.local_ids)
                            if se.defined:
                                defined.extend(se.local_ids)
                            stack_modified = True
                        case teal.StackDefine() as sd:
                            defined.append(sd.local_id)
                        case teal.StackInsert() as si:
                            index = len(stack) - si.depth
                            stack.insert(index, si.local_id)
                            defined.append(si.local_id)
                            stack_modified = True
                        case teal.StackPop() as sp:
                            index = len(stack) - sp.depth - 1
                            stack.pop(index)
                            stack_modified = True
                        case _:
                            typing.assert_never(sm)

                if defined:
                    update_event(defined_out=sorted(set(defined) & set(stack)))
                if stack_modified:
                    update_event(stack_out=stack.copy())
                avm_op = lower_op(ctx, op)
                match avm_op:
                    case models.Jump(op_code="callsub", label=models.Label(name=func_block)):
                        update_event(callsub=function_block_ids[func_block])
                    case models.Intrinsic(op_code="retsub"):
                        update_event(retsub=True)
                update_event(op=avm_op.accept(OpDescription()))
                avm_ops.append(avm_op)
    return avm_ops


def lower_op(ctx: AssembleContext, op: teal.TealOp) -> models.AVMOp:
    # TODO: use visitor pattern, and simplify assemble ops since constant gathering is now done
    # at the teal level
    match op:
        case teal.TemplateVar():
            raise InternalError(
                "template vars should already be in constant block", op.source_location
            )
        case teal.IntBlock(constants=constants, source_location=loc):
            return models.IntBlock(
                constants=_resolve_template_vars(ctx, int, constants.items()),
                source_location=loc,
            )
        case teal.IntC(index=index, source_location=loc):
            return models.IntC(
                index=index,
                source_location=loc,
            )
        case teal.PushInt(value=int(int_value)) | teal.Int(value=int(int_value)):
            return models.PushInt(value=int_value, source_location=op.source_location)
        case teal.Int(value=str(int_alias)):
            try:
                int_value = TEAL_ALIASES[int_alias]
            except KeyError as ex:
                raise InternalError(f"Unknown teal alias: {int_alias}", op.source_location) from ex
            return models.PushInt(value=int_value, source_location=op.source_location)
        case teal.PushInts(values=values, source_location=loc):
            return models.PushInts(
                values=values,
                source_location=loc,
            )
        case teal.BytesBlock(constants=constants, source_location=loc):
            return models.BytesBlock(
                constants=_resolve_template_vars(
                    ctx, bytes, [(b, es[1]) for b, es in constants.items()]
                ),
                source_location=loc,
            )
        case teal.BytesC(index=index, source_location=loc):
            return models.BytesC(
                index=index,
                source_location=loc,
            )
        case teal.PushBytes(value=bytes_value) | teal.Byte(value=bytes_value):
            return models.PushBytes(value=bytes_value, source_location=op.source_location)
        case teal.PushBytess(values=values, source_location=loc):
            return models.PushBytess(
                values=[b for b, _ in values],
                source_location=loc,
            )
        case teal.CallSub(target=label_id, op_code=op_code, source_location=loc):
            return models.Jump(
                op_code=op_code, label=models.Label(name=label_id), source_location=loc
            )
        case teal.TealOp(
            op_code="b" | "bz" | "bnz" as op_code, immediates=immediates, source_location=loc
        ):
            try:
                (maybe_label_id,) = immediates
            except ValueError:
                maybe_label_id = None
            if not isinstance(maybe_label_id, str):
                raise InternalError(
                    f"Invalid op code: {op.teal()}",
                    loc,
                )
            return models.Jump(
                op_code=op_code, label=models.Label(name=maybe_label_id), source_location=loc
            )
        case teal.TealOp(
            op_code="switch" | "match" as op_code,
            immediates=immediates,
            source_location=loc,
        ):
            labels = list[str]()
            for maybe_label in immediates:
                if not isinstance(maybe_label, str):
                    raise InternalError(
                        f"Invalid op code: {op.teal()}",
                        loc,
                    )
                labels.append(maybe_label)
            return models.MultiJump(
                op_code=op_code,
                labels=[models.Label(label) for label in labels],
                source_location=loc,
            )
        case teal.TealOp(op_code=op_code, immediates=immediates, source_location=loc):
            return models.Intrinsic(op_code=op_code, immediates=immediates, source_location=loc)
        case _:
            typing.assert_never()


_T = typing.TypeVar("_T")


def _resolve_template_vars(
    ctx: AssembleContext, typ: type[_T], values: Iterable[tuple[_T | str, SourceLocation | None]]
) -> Sequence[_T]:
    result = []
    for value_or_template, var_loc in values:
        if not isinstance(value_or_template, str):
            value: _T = value_or_template
        else:
            try:
                maybe_value, val_loc = ctx.template_variables[value_or_template]
            except KeyError:
                raise CodeError(
                    f"template variable not defined: {value_or_template}", var_loc
                ) from None
            if not isinstance(maybe_value, typ):
                raise CodeError(
                    f"invalid template value type for {value_or_template!r},"
                    f" expected {typ.__name__}",
                    val_loc or var_loc,
                )
            value = maybe_value
        result.append(value)
    return result
