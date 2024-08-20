import re
import typing
from collections.abc import Sequence

import attrs
import mypy.nodes

from puya import arc4_util, log
from puya.awst_build import arc4_utils, pytypes
from puya.awst_build.arc4_utils import pytype_to_arc4_pytype
from puya.awst_build.eb import _expect as expect
from puya.awst_build.eb._utils import dummy_value
from puya.awst_build.eb.factories import builder_for_type
from puya.awst_build.eb.interface import InstanceBuilder, LiteralBuilder, NodeBuilder
from puya.awst_build.utils import maybe_resolve_literal
from puya.errors import CodeError, InternalError
from puya.parse import SourceLocation

logger = log.get_logger(__name__)

_VALID_NAME_PATTERN = re.compile("^[_A-Za-z][A-Za-z0-9_]*$")


@attrs.frozen
class ARC4Signature:
    method_name: str
    arg_types: Sequence[pytypes.PyType] = attrs.field(converter=tuple[pytypes.PyType, ...])
    return_type: pytypes.PyType | None

    @property
    def method_selector(self) -> str:
        args = ",".join(map(arc4_utils.pytype_to_arc4, self.arg_types))
        return_type = arc4_utils.pytype_to_arc4(self.return_type or pytypes.NoneType)
        return f"{self.method_name}({args}){return_type}"

    def convert_args(
        self, native_args: Sequence[NodeBuilder], location: SourceLocation
    ) -> Sequence[InstanceBuilder]:
        num_args = len(native_args)
        num_sig_args = len(self.arg_types)
        if num_sig_args != num_args:
            logger.error(
                f"expected {num_sig_args} ABI argument{'' if num_sig_args == 1 else 's'},"
                f" got {num_args}",
                location=location,
            )
        arc4_args = [
            _implicit_arc4_conversion(arg, pt)
            for arg, pt in zip(native_args, self.arg_types, strict=False)
        ]
        return arc4_args


def get_arc4_signature(
    method: NodeBuilder, native_args: Sequence[NodeBuilder], loc: SourceLocation
) -> tuple[str, ARC4Signature]:
    method = expect.argument_of_type(method, pytypes.StrLiteralType, default=expect.default_raise)
    match method:
        case LiteralBuilder(value=str(method_sig)):
            pass
        case _:
            raise CodeError("method selector must be a simple str literal", method.source_location)

    method_name, maybe_args, maybe_returns = _split_signature(method_sig, method.source_location)
    if maybe_args is None:
        arg_types = [
            _implicit_arc4_type_conversion(
                expect.instance_builder(na, default=expect.default_raise).pytype, loc
            )
            for na in native_args
        ]
    elif maybe_args:
        arg_types = [
            arc4_utils.arc4_to_pytype(a, loc) for a in arc4_util.split_tuple_types(maybe_args)
        ]
    else:  # args are specified but empty
        arg_types = []
    return_type = arc4_utils.arc4_to_pytype(maybe_returns, loc) if maybe_returns else None
    return method_sig, ARC4Signature(method_name, arg_types, return_type)


def _implicit_arc4_type_conversion(typ: pytypes.PyType, loc: SourceLocation) -> pytypes.PyType:
    match typ:
        case pytypes.StrLiteralType:
            return pytypes.ARC4StringType
        case pytypes.BytesLiteralType:
            return pytypes.ARC4DynamicBytesType
        case pytypes.IntLiteralType:
            return pytypes.ARC4UIntN_Aliases[64]

    def on_error(invalid_pytype: pytypes.PyType) -> typing.Never:
        raise CodeError(
            f"{invalid_pytype} is not an ARC4 type and no implicit ARC4 conversion possible", loc
        )

    return pytype_to_arc4_pytype(typ, on_error)


def _implicit_arc4_conversion(
    operand: NodeBuilder, target_type: pytypes.PyType
) -> InstanceBuilder:
    from puya.awst.wtypes import ARC4Type

    instance = expect.instance_builder(operand, default=expect.default_dummy_value(target_type))
    instance = maybe_resolve_literal(instance, target_type)
    if instance.pytype == target_type:
        return instance
    target_wtype = target_type.wtype
    if not isinstance(target_wtype, ARC4Type):
        raise InternalError(
            "implicit_operand_conversion expected target_type to be an ARC-4 type,"
            f" got {target_type}",
            instance.source_location,
        )
    if isinstance(instance.pytype.wtype, ARC4Type):
        logger.error(
            f"expected type {target_type}, got type {instance.pytype}",
            location=instance.source_location,
        )
        return dummy_value(target_type, instance.source_location)
    if instance.pytype.wtype not in target_wtype.encodeable_types:
        logger.error(
            f"cannot encode {instance.pytype} to {target_type}", location=instance.source_location
        )
        return dummy_value(target_type, instance.source_location)
    target_type_builder = builder_for_type(target_type, instance.source_location)
    return target_type_builder.call(
        args=[instance],
        arg_names=[None],
        arg_kinds=[mypy.nodes.ARG_POS],
        location=instance.source_location,
    )


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


def no_literal_items(array_type: pytypes.ArrayType, location: SourceLocation) -> None:
    if isinstance(array_type.items, pytypes.LiteralOnlyType):
        raise CodeError("arrays of literals are not supported", location)
