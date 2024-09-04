import typing

import attrs

from puya import algo_constants, log
from puya.errors import CodeError, InternalError
from puya.models import OnCompletionAction, TransactionType
from puya.teal import models as teal
from puya.ussemble import models
from puya.ussemble.context import AssembleContext
from puya.ussemble.debug import Event
from puya.ussemble.desc_visitor import OpDescription
from puya.utils import Address, method_selector_hash

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
        f_stack = list[str]()
        for block in subroutine.blocks:
            update_event(
                block=block.label,
                x_stack_in=block.x_stack,
            )
            x_stack = list(block.x_stack)
            l_stack = list[str]()
            avm_ops.append(models.Label(name=block.label))
            for op in block.ops:
                stacks = {}
                defined = []
                for sm in op.stack_manipulations:
                    match sm.stack:
                        case "f":
                            stack = f_stack
                        case "x":
                            stack = x_stack
                        case "l":
                            stack = l_stack
                        case _:
                            typing.assert_never(sm.stack)
                    if sm.manipulation in ("insert", "pop"):
                        stacks[f"{sm.stack}_stack_out"] = stack
                    match sm.manipulation:
                        case "insert":
                            stack.insert(sm.index, sm.local_id)
                            if sm.defined:  # f-stack allocates variables before they are defined
                                defined.append(sm.local_id)
                        case "pop":
                            stack.pop(sm.index)
                        case "define":
                            defined.append(sm.local_id)
                        case _:
                            typing.assert_never(sm.manipulation)
                if defined:
                    available = {*f_stack, *x_stack, *l_stack}
                    update_event(defined_out=sorted(set(defined) & available))
                for name, value in stacks.items():
                    update_event(**{name: list(value)})
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
    match op:
        case teal.Int(value=int(int_value), source_location=loc):
            return models.PushInt(value=int_value, source_location=loc)
        case teal.Int(value=str(int_alias), source_location=loc):
            try:
                int_value = TEAL_ALIASES[int_alias]
            except KeyError as ex:
                raise InternalError(f"Unknown teal alias: {int_alias}", op.source_location) from ex
            return models.PushInt(value=int_value, source_location=loc)
        case teal.Byte(value=bytes_value, source_location=loc):
            return models.PushBytes(value=bytes_value, source_location=loc)
        case teal.Method(value=method_value, source_location=loc):
            return models.PushBytes(value=method_selector_hash(method_value), source_location=loc)
        case teal.Address(value=address_value, source_location=loc):
            address = Address.parse(address_value)
            if not address.is_valid:
                raise InternalError(f"Invalid address literal: {address_value}", loc)
            return models.PushBytes(value=address.public_key, source_location=loc)
        case teal.TemplateVar(name=name, op_code=op_code, source_location=var_loc):
            try:
                value, value_loc = ctx.template_variables[name]
            except KeyError as ex:
                raise CodeError(f"template value not defined: {name!r}", var_loc) from ex
            else:
                match value, op_code:
                    case int(int_value), "int":
                        if int_value < 0 or int_value.bit_length() > 64:
                            logger.error(
                                f"template uint64 value out of range: {name!r}", location=value_loc
                            )
                            logger.info("affected variable", location=var_loc)
                        return models.PushInt(value=int_value, source_location=var_loc)
                    case bytes(byte_value), "byte":
                        if len(byte_value) > algo_constants.MAX_BYTES_LENGTH:
                            logger.error(
                                f"template bytes value too long: {name!r}", location=value_loc
                            )
                            logger.info("affected variable", location=var_loc)
                        return models.PushBytes(value=byte_value, source_location=var_loc)
                    case _:
                        expected = "uint64" if op_code == "int" else "bytes"
                        raise CodeError(
                            f"invalid template value type for {name!r}, expected {expected}",
                            value_loc or var_loc,
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
