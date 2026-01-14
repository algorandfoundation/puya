from collections.abc import Mapping, Sequence, Set
from itertools import zip_longest

from puya import log
from puya.algo_constants import MAX_UINT64
from puya.awst.txn_fields import TxnField
from puya.errors import CodeError
from puya.parse import SourceLocation
from puya.utils import StableSet
from puyapy.awst_build import pytypes
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    LiteralBuilder,
    NodeBuilder,
)
from puyapy.awst_build.eb.transaction.itxn_args import PYTHON_ITXN_ARGUMENTS
from puyapy.awst_build.eb.tuple import TupleLiteralBuilder
from puyapy.awst_build.utils import maybe_resolve_literal as base_maybe_resolve_literal

logger = log.get_logger(__name__)


def get_method_abi_args_and_kwargs(
    args: Sequence[NodeBuilder], arg_names: list[str | None], allowed_kwargs: Set[str]
) -> tuple[NodeBuilder | None, Sequence[NodeBuilder], dict[str, NodeBuilder]]:
    method: NodeBuilder | None = None
    abi_args = list[NodeBuilder]()
    kwargs = dict[str, NodeBuilder]()
    for idx, (arg_name, arg) in enumerate(zip(arg_names, args, strict=True)):
        if arg_name is None:
            if idx == 0:
                method = arg
            else:
                abi_args.append(arg)
        elif arg_name in allowed_kwargs:
            kwargs[arg_name] = arg
        else:
            logger.error("unrecognised keyword argument", location=arg.source_location)
    return method, abi_args, kwargs


def get_python_kwargs(fields: Sequence[TxnField]) -> Set[str]:
    return StableSet.from_iter(
        arg for arg, param in PYTHON_ITXN_ARGUMENTS.items() if param.field in fields
    )


def maybe_convert_literal_and_itxn_field(
    typ: pytypes.PyType, location: SourceLocation
) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.StringType
        case pytypes.BytesLiteralType:
            return pytypes.BytesType
        case pytypes.IntLiteralType:
            return pytypes.UInt64Type
        case pytypes.TupleType:
            return pytypes.GenericTupleType.parameterise(
                [maybe_convert_literal_and_itxn_field(t, location) for t in typ.items],
                source_location=location,
            )
        # convert an inner txn type to the equivalent group txn type
        case pytypes.InnerTransactionFieldsetType(transaction_type=txn_type):
            return pytypes.GroupTransactionTypes[txn_type]
        case _:
            return typ


def maybe_resolve_literal(
    operand: InstanceBuilder,
    *,
    expected_type: pytypes.PyType | None = None,
    allow_literal: bool = True,
) -> InstanceBuilder:
    if isinstance(operand, TupleLiteralBuilder):
        item_types = list[pytypes.PyType]()
        if expected_type is not None and isinstance(expected_type, pytypes.TupleType):
            item_types.extend(expected_type.items)
        resolved_items = [
            maybe_resolve_literal(elem, expected_type=item_type, allow_literal=allow_literal)
            for elem, item_type in zip_longest(operand.iterate_static(), item_types)
        ]
        return TupleLiteralBuilder(resolved_items, operand.source_location)

    if expected_type is None:
        match operand.pytype:
            case pytypes.StrLiteralType:
                typ: pytypes.PyType = pytypes.StringType
            case pytypes.BytesLiteralType:
                typ = pytypes.BytesType
            case pytypes.IntLiteralType:
                if (
                    (isinstance(operand, LiteralBuilder))
                    and isinstance(operand.value, int)
                    and operand.value > MAX_UINT64
                ):
                    typ = pytypes.BigUIntType
                else:
                    typ = pytypes.UInt64Type
            case pytypes.GroupTransactionType() | pytypes.InnerTransactionResultType():
                raise CodeError(
                    f"cannot use {operand.pytype} as an argument to an ARC-4 method",
                    location=operand.source_location,
                )
            case _:
                typ = operand.pytype
        if (typ != operand.pytype) and not allow_literal:
            logger.error(
                "type information is needed when passing a literal value",
                location=operand.source_location,
            )
    else:
        typ = expected_type

    return base_maybe_resolve_literal(operand, typ)


def is_creating(field_nodes: Mapping[TxnField, NodeBuilder]) -> bool | None:
    """
    Returns app_id == 0 if app_id is statically known, otherwise returns None
    """
    match field_nodes.get(TxnField.ApplicationID):
        case None:
            return True
        case LiteralBuilder(value=int(app_id)):
            return app_id == 0
    return None
