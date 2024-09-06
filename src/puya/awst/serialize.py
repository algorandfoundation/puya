import decimal
import enum
import functools
import typing
from collections.abc import Mapping

import cattrs
from cattrs import ClassValidationError, IterableValidationError, transform_error
from cattrs.preconf.json import make_converter
from cattrs.strategies import configure_tagged_union, include_subclasses
from immutabledict import immutabledict

from puya import log
from puya.awst import nodes, txn_fields, wtypes
from puya.utils import StableSet

logger = log.get_logger(__name__)


def _unstructure_optional_enum_literal(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, enum.Enum):
        raise TypeError("expected enum value")
    return value.value


@functools.cache
def _get_converter() -> cattrs.preconf.json.JsonConverter:
    converter = make_converter()

    # literals with optional enum
    converter.register_unstructure_hook_factory(
        cattrs.converters.is_literal_containing_enums, lambda _: _unstructure_optional_enum_literal
    )

    # TxnField and PuyaLibFunction as name
    for enum_type in (txn_fields.TxnField, nodes.PuyaLibFunction):
        converter.register_unstructure_hook(enum_type, lambda v: v.name)
        converter.register_structure_hook(enum_type, lambda v, t: t[v])

    # decimals as str
    converter.register_unstructure_hook(decimal.Decimal, str)
    converter.register_structure_hook(decimal.Decimal, lambda v, _: decimal.Decimal(v))

    # stable set
    def is_stableset(typ: type) -> bool:
        return issubclass(typing.get_origin(typ) or typ, StableSet)

    converter.register_unstructure_hook_factory(is_stableset, converter.gen_unstructure_iterable)
    converter.register_structure_hook_factory(
        is_stableset, lambda _: lambda i, _: StableSet.from_iter(i)
    )

    # nodes.Switch has a mapping of Expression -> Block
    # which can't be serialized with that structure as a JSON object
    # need to convert into a list of pairs instead
    def is_switch_cases(typ: object) -> bool:
        if typing.get_origin(typ) is Mapping:
            args = typing.get_args(typ)
            return args == (nodes.Expression, nodes.Block)
        return False

    def unstructure_switch_cases(value: Mapping[nodes.Expression, nodes.Block]) -> object:
        return converter.unstructure(value.items(), list[tuple[nodes.Expression, nodes.Block]])

    def structure_switch_cases(value: object, _: type) -> object:
        items = converter.structure(value, list[tuple[nodes.Expression, nodes.Block]])
        return immutabledict(items)

    converter.register_unstructure_hook_func(is_switch_cases, unstructure_switch_cases)
    converter.register_structure_hook_func(is_switch_cases, structure_switch_cases)

    # register AWST types and unions, order is important to ensure correct configuration
    union_strategy = configure_tagged_union
    include_subclasses(wtypes.WType, converter, union_strategy=union_strategy)
    union_strategy(wtypes.WStructType | wtypes.ARC4Struct, converter)
    union_strategy(nodes.SubroutineTarget, converter)
    include_subclasses(nodes.Expression, converter, union_strategy=union_strategy)
    union_strategy(nodes.Lvalue, converter)
    union_strategy(nodes.StorageExpression, converter)
    union_strategy(nodes.CompileTimeConstantExpression, converter)
    include_subclasses(nodes.Statement, converter, union_strategy=union_strategy)
    include_subclasses(nodes.RootNode, converter, union_strategy=union_strategy)
    return converter


def awst_to_json(awst: nodes.AWST) -> str:
    return _get_converter().dumps(awst, indent=4)


def awst_from_json(json: str) -> nodes.AWST:
    try:
        return _get_converter().loads(json, nodes.AWST)  # type: ignore[type-abstract]
    except (ClassValidationError, IterableValidationError) as err:
        logger.debug("Deserialization error: \n" + "\n".join(transform_error(err)))
        raise ValueError(
            "Error during deserialization of AWST json. See debug log for details"
        ) from err
