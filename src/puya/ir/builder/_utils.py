import re
from collections.abc import Sequence

from puya import log
from puya.awst import (
    nodes as awst_nodes,
)
from puya.errors import CodeError
from puya.ir.models import (
    TMP_VAR_INDICATOR,
    Register,
    Undefined,
    Value,
    ValueProvider,
    ValueTuple,
)
from puya.ir.op_utils import assign_targets, mktemp
from puya.ir.register_context import IRRegisterContext
from puya.ir.types_ import IRType, TupleIRType, ir_type_to_ir_types, wtype_to_abi_name
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")
_ARRAY_PATTERN = re.compile(r"^\[[0-9]*]$")


def assign(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    name: str,
    ir_type: IRType | None = None,
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> Register:
    if ir_type is None:
        (ir_type,) = source.types
    target = context.new_register(name, ir_type, register_location or assignment_location)
    assign_targets(
        context=context,
        source=source,
        targets=[target],
        assignment_location=assignment_location,
    )
    return target


def assign_tuple(
    context: IRRegisterContext,
    source: ValueProvider,
    *,
    names: Sequence[str],
    ir_types: Sequence[IRType] | None = None,
    assignment_location: SourceLocation | None,
    register_location: SourceLocation | None = None,
) -> list[Register]:
    if ir_types is None:
        ir_types = source.types
    if register_location is None:
        register_location = assignment_location
    targets = [
        context.new_register(name, ir_type, register_location)
        for name, ir_type in zip(names, ir_types, strict=True)
    ]
    assign_targets(
        context=context,
        source=source,
        targets=targets,
        assignment_location=assignment_location,
    )
    return targets


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


def get_implicit_return_is_original(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}is_original"


def get_implicit_return_out(var_name: str) -> str:
    return f"{var_name}{TMP_VAR_INDICATOR}out"


def undefined_value(typ: IRType | TupleIRType, loc: SourceLocation) -> Value | ValueTuple:
    if not isinstance(typ, TupleIRType):
        return Undefined(ir_type=typ, source_location=loc)
    else:
        ir_types = ir_type_to_ir_types(typ)
        values = [Undefined(ir_type=ir_type, source_location=loc) for ir_type in ir_types]
        return ValueTuple(values=values, ir_type=typ, source_location=loc)


def method_signature_to_abi_signature(value: awst_nodes.MethodSignature) -> str:
    name = value.name
    arg_abi_names = [
        wtype_to_abi_name(
            t, resource_encoding=value.resource_encoding, source_location=value.source_location
        )
        for t in value.arg_types or []
    ]
    args = ",".join(arg_abi_names)
    return_ = wtype_to_abi_name(value.return_type, source_location=value.source_location)
    signature = f"{name}({args}){return_}"
    return signature


def split_signature(
    signature: str, location: SourceLocation
) -> tuple[str, str | None, str | None]:
    """Splits signature into name, args and returns"""
    level = 0
    last_idx = 0
    name: str = ""
    args: str | None = None
    returns: str | None = None
    for idx, tok in enumerate(signature):
        if tok == "(":
            level += 1
            if level == 1:
                if not name:
                    name = signature[:idx]
                last_idx = idx + 1
        elif tok == ")":
            level -= 1
            if level == 0:
                if args is None:
                    args = signature[last_idx:idx]
                elif returns is None:
                    returns = signature[last_idx - 1 : idx + 1]
                last_idx = idx + 1
    if last_idx < len(signature):
        remaining = signature[last_idx:]
        if remaining:
            if returns is not None and _ARRAY_PATTERN.match(remaining):
                returns += remaining
            elif not name:
                name = remaining
            elif args is None:
                raise CodeError(
                    f"invalid signature, args not well defined: {name=}, {remaining=}", location
                )
            elif returns:
                raise CodeError(
                    f"invalid signature, text after returns:"
                    f" {name=}, {args=}, {returns=}, {remaining=}",
                    location,
                )
            else:
                returns = remaining
    if not name or not _VALID_NAME_PATTERN.match(name):
        logger.error(f"invalid signature: {name=}", location=location)
    return name, args, returns
