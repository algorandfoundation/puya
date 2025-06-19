import decimal
import enum
import functools
import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import cattrs
from cattrs import ClassValidationError, IterableValidationError, transform_error
from cattrs.preconf.json import make_converter
from cattrs.strategies import configure_tagged_union, include_subclasses
from immutabledict import immutabledict

from puya import log
from puya.awst import nodes, txn_fields, wtypes
from puya.errors import PuyaError

logger = log.get_logger(__name__)


def _unstructure_optional_enum_literal(value: object) -> object:
    if value is None:
        return None
    if not isinstance(value, enum.Enum):
        raise TypeError("expected enum value")
    return value.value


@functools.cache
def get_converter() -> cattrs.preconf.json.JsonConverter:
    converter = make_converter()

    # literals with optional enum
    converter.register_unstructure_hook_factory(
        cattrs.converters.is_literal_containing_enums, lambda _: _unstructure_optional_enum_literal
    )

    # TxnField and PuyaLibFunction as name
    for enum_type in (txn_fields.TxnField, nodes.PuyaLibFunction, log.LogLevel):
        converter.register_unstructure_hook(enum_type, lambda v: v.name)
        converter.register_structure_hook(enum_type, lambda v, t: t[v])

    # decimals as str
    converter.register_unstructure_hook(decimal.Decimal, str)
    converter.register_structure_hook(decimal.Decimal, lambda v, _: decimal.Decimal(v))

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
    union_strategy(
        wtypes.ARC4DynamicArray
        | wtypes.ARC4StaticArray
        | wtypes.StackArray
        | wtypes.ReferenceArray,
        converter,
    )
    include_subclasses(nodes.Expression, converter, union_strategy=union_strategy)
    union_strategy(nodes.Lvalue, converter)
    union_strategy(nodes.StorageExpression, converter)
    union_strategy(nodes.CompileTimeConstantExpression, converter)
    include_subclasses(nodes.Statement, converter, union_strategy=union_strategy)
    include_subclasses(nodes.RootNode, converter, union_strategy=union_strategy)
    return converter


def awst_to_json(awst: nodes.AWST) -> str:
    return get_converter().dumps(awst, indent=4)


def _find_and_log_puya_errors(err: ClassValidationError | IterableValidationError) -> None:
    for ex in err.exceptions:
        match ex:
            case PuyaError():
                logger.error(ex.msg, location=ex.location)
            case ClassValidationError() | IterableValidationError():
                _find_and_log_puya_errors(ex)


def awst_from_json(json: str) -> nodes.AWST:
    try:
        return get_converter().loads(json, nodes.AWST)  # type: ignore[type-abstract]
    except (ClassValidationError, IterableValidationError) as err:
        _find_and_log_puya_errors(err)
        logger.debug("Deserialization error: \n" + "\n".join(transform_error(err)))
        raise ValueError(
            "Error during deserialization of AWST json. See debug log for details"
        ) from err


def source_annotations_to_json(sources_by_path: Mapping[Path, Sequence[str] | None]) -> str:
    return get_converter().dumps(sources_by_path, indent=4)


def source_annotations_from_json(json: str) -> dict[Path, list[str] | None]:
    return get_converter().loads(json, dict[Path, list[str] | None])
