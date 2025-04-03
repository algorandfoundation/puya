import re
import typing
from collections.abc import Sequence

import attrs

from puya import log
from puya.awst import (
    nodes as awst_nodes,
    wtypes,
)
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation
from puyapy import models
from puyapy.awst_build import arc4_utils, pytypes
from puyapy.awst_build.arc4_utils import pytype_to_arc4_pytype, split_tuple_types
from puyapy.awst_build.eb import _expect as expect
from puyapy.awst_build.eb._utils import dummy_value
from puyapy.awst_build.eb.factories import builder_for_instance, builder_for_type
from puyapy.awst_build.eb.interface import (
    InstanceBuilder,
    NodeBuilder,
    StaticSizedCollectionBuilder,
)
from puyapy.awst_build.utils import maybe_resolve_literal

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


def _pytype_to_arc4_return_pytype(typ: pytypes.PyType, sig: attrs.AttrsInstance) -> pytypes.PyType:
    assert isinstance(sig, ARC4Signature)

    def on_error(bad_type: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"invalid return type for an ARC-4 method: {bad_type}", sig.source_location
        )

    return arc4_utils.pytype_to_arc4_pytype(typ, on_error, encode_resource_types=True)


def _pytypes_to_arc4_arg_pytypes(
    types: Sequence[pytypes.PyType], sig: attrs.AttrsInstance
) -> Sequence[pytypes.PyType]:
    assert isinstance(sig, ARC4Signature)

    def on_error(bad_type: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"invalid argument type for an ARC-4 method: {bad_type}", sig.source_location
        )

    return tuple(pytype_to_arc4_pytype(t, on_error, encode_resource_types=False) for t in types)


@attrs.frozen(kw_only=True)
class ARC4Signature:
    source_location: SourceLocation | None
    method_name: str
    arg_types: Sequence[pytypes.PyType] = attrs.field(
        converter=attrs.Converter(_pytypes_to_arc4_arg_pytypes, takes_self=True)  # type: ignore[misc]
    )
    return_type: pytypes.PyType = attrs.field(
        converter=attrs.Converter(_pytype_to_arc4_return_pytype, takes_self=True)  # type: ignore[misc]
    )

    @property
    def method_selector(self) -> str:
        args = ",".join(
            arc4_utils.pytype_to_arc4(t, encode_resource_types=False) for t in self.arg_types
        )
        return_type = arc4_utils.pytype_to_arc4(self.return_type, encode_resource_types=True)
        return f"{self.method_name}({args}){return_type}"

    def convert_args(
        self,
        native_args: Sequence[NodeBuilder],
        *,
        expect_itxn_args: bool = False,
    ) -> Sequence[InstanceBuilder]:
        num_args = len(native_args)
        num_sig_args = len(self.arg_types)
        if num_sig_args != num_args:
            logger.error(
                f"expected {num_sig_args} ABI argument{'' if num_sig_args == 1 else 's'},"
                f" got {num_args}",
                location=self.source_location,
            )
        arg_types = (
            list(map(_gtxn_to_itxn, self.arg_types)) if expect_itxn_args else self.arg_types
        )
        arc4_args = [
            _implicit_arc4_conversion(arg, pt)
            for arg, pt in zip(native_args, arg_types, strict=False)
        ]
        return arc4_args


def _gtxn_to_itxn(pytype: pytypes.PyType) -> pytypes.PyType:
    if isinstance(pytype, pytypes.GroupTransactionType):
        return pytypes.InnerTransactionFieldsetTypes[pytype.transaction_type]
    return pytype


def get_arc4_signature(
    method: NodeBuilder, native_args: Sequence[NodeBuilder], loc: SourceLocation
) -> tuple[str, ARC4Signature]:
    method_sig = expect.simple_string_literal(method, default=expect.default_raise)
    method_name, maybe_args, maybe_returns = _split_signature(method_sig, method.source_location)
    if maybe_args is None:
        arg_types = [
            _implicit_arc4_type_arg_conversion(
                expect.instance_builder(na, default=expect.default_raise).pytype, loc
            )
            for na in native_args
        ]
    elif maybe_args:
        arg_types = [arc4_utils.arc4_to_pytype(a, loc) for a in split_tuple_types(maybe_args)]
    else:  # args are specified but empty
        arg_types = []
    return_type = (
        arc4_utils.arc4_to_pytype(maybe_returns, loc) if maybe_returns else pytypes.NoneType
    )
    return method_sig, ARC4Signature(
        method_name=method_name, arg_types=arg_types, return_type=return_type, source_location=loc
    )


def _implicit_arc4_type_arg_conversion(typ: pytypes.PyType, loc: SourceLocation) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.ARC4StringType
        case pytypes.BytesLiteralType:
            return pytypes.ARC4DynamicBytesType
        case pytypes.IntLiteralType:
            return pytypes.ARC4UIntN_Aliases[64]
        # convert an inner txn type to the equivalent group txn type
        case pytypes.InnerTransactionFieldsetType(transaction_type=txn_type):
            return pytypes.GroupTransactionTypes[txn_type]

    def on_error(invalid_pytype: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"{invalid_pytype} is not an ARC-4 type and no implicit ARC-4 conversion possible", loc
        )

    return pytype_to_arc4_pytype(typ, on_error, encode_resource_types=False)


def _inner_transaction_type_matches(instance: pytypes.PyType, target: pytypes.PyType) -> bool:
    if not isinstance(instance, pytypes.InnerTransactionFieldsetType):
        return False
    if not isinstance(target, pytypes.InnerTransactionFieldsetType):
        return False
    return (
        instance.transaction_type == target.transaction_type
        or instance.transaction_type is None
        or target.transaction_type is None
    )


def _implicit_arc4_conversion(
    operand: NodeBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    instance = expect.instance_builder(operand, default=expect.default_dummy_value(target_type))
    instance = _maybe_resolve_arc4_literal(instance, target_type)
    if target_type <= instance.pytype:
        return instance
    target_wtype = target_type.wtype
    if isinstance(target_type, pytypes.TransactionRelatedType):
        if _inner_transaction_type_matches(instance.pytype, target_type):
            return instance
        else:
            logger.error(
                f"expected type {target_type}, got type {instance.pytype}",
                location=instance.source_location,
            )
            return dummy_value(target_type, instance.source_location)
    if not isinstance(target_wtype, wtypes.ARC4Type):
        raise InternalError(
            "implicit_operand_conversion expected target_type to be an ARC-4 type,"
            f" got {target_type}",
            instance.source_location,
        )
    instance_wtype = instance.pytype.checked_wtype(instance.source_location)
    if isinstance(instance_wtype, wtypes.ARC4Type):
        logger.error(
            f"expected type {target_type}, got type {instance.pytype}",
            location=instance.source_location,
        )
        return dummy_value(target_type, instance.source_location)
    if (
        isinstance(target_type, pytypes.StructType)
        and isinstance(instance.pytype, pytypes.TupleType)
        and len(target_type.types) == len(instance.pytype.items)
    ):
        # Special handling to map tuples (named and unnamed) to arc4 structs
        # instance builder for TupleType should be a StaticSizedCollectionBuilder
        assert isinstance(instance, StaticSizedCollectionBuilder)
        conversion_args = [
            _implicit_arc4_conversion(item, item_target_typ)
            for item, item_target_typ in zip(
                instance.iterate_static(), target_type.types, strict=True
            )
        ]
        target_type_builder = builder_for_type(target_type, instance.source_location)
        return target_type_builder.call(
            args=conversion_args,
            arg_names=[None] * len(conversion_args),
            arg_kinds=[models.ArgKind.ARG_POS] * len(conversion_args),
            location=instance.source_location,
        )
    encoded = awst_nodes.ARC4Encode(
        value=instance.resolve(),
        wtype=target_wtype,
        source_location=instance.source_location,
    )
    return builder_for_instance(target_type, encoded)


def _maybe_resolve_arc4_literal(
    operand: InstanceBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    """Handles special case of resolving a literal tuple into an arc4 tuple"""
    from puyapy.awst_build.eb.tuple import TupleLiteralBuilder

    if isinstance(operand, TupleLiteralBuilder) and isinstance(target_type, pytypes.ARC4TupleType):
        resolved_items = [
            _maybe_resolve_arc4_literal(item, item_type)
            for item, item_type in zip(operand.iterate_static(), target_type.items, strict=True)
        ]
        return TupleLiteralBuilder(resolved_items, operand.source_location)
    return maybe_resolve_literal(operand, target_type)


def _split_signature(
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
            if not name:
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
