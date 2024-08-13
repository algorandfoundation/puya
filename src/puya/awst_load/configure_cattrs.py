import collections.abc
import inspect
import typing

import attrs
from cattrs import Converter
from cattrs.gen import make_dict_structure_fn
from cattrs.strategies import configure_tagged_union
from immutabledict import immutabledict

from puya.awst import (
    wtypes,
    nodes as awst_nodes,
)
from puya.parse import SourceLocation
from puya.utils import StableSet


def _make_subclasses_tree(cl: type) -> list[type]:
    return [cl] + [sscl for scl in type.__subclasses__(cl) for sscl in _make_subclasses_tree(scl)]


nodes_map = {}

wtypes_map = {}

for cls in _make_subclasses_tree(awst_nodes.Node):
    nodes_map[cls.__name__] = cls


for cls in _make_subclasses_tree(wtypes.WType):
    wtypes_map[cls.__name__] = cls


def build_node_structure_func(
    converter: Converter,
) -> typing.Callable[[typing.Mapping[str, typing.Any], typing.Any], typing.Any]:
    def structure_func(data: typing.Mapping[str, typing.Any], cls: type) -> typing.Any:

        if "_type" in data and data["_type"] in nodes_map:
            node_type = nodes_map[data["_type"]]

            # Add None for any missing optional fields
            data_with_optional_fields = {
                field.name: data.get(field.name, None) for field in attrs.fields(node_type)
            }

            return make_dict_structure_fn(
                node_type,
                converter,
            )(data_with_optional_fields, node_type)
        else:
            return make_dict_structure_fn(cls, converter)(data, cls)

    return structure_func


def build_wtype_structure_func(
    converter: Converter,
) -> typing.Callable[[typing.Mapping[str, typing.Any], typing.Any], typing.Any]:
    def structure_func(data: typing.Mapping[str, typing.Any], cls: type) -> typing.Any:

        if "_type" in data and data["_type"] in wtypes_map:
            wtype = wtypes_map[data["_type"]]

            # Add None for any missing optional fields
            data_with_optional_fields = {
                field.name: data.get(field.name, None) for field in attrs.fields(wtype)
            }

            match wtype:
                case wtypes.WTuple:
                    return wtypes.WTuple(
                        types=converter.structure(data.get("types", None), list[wtypes.WType]),
                        source_location=converter.structure(
                            data.get("source_location", None), SourceLocation | None
                        ),
                    )
                case wtypes.ARC4UIntN:
                    return wtypes.ARC4UIntN(
                        alias=converter.structure(data.get("alias", None), str),
                        n=converter.structure(data.get("n", None), int),
                        decode_type=converter.structure(
                            data.get("decode_type", None), wtypes.WType
                        ),
                        source_location=converter.structure(
                            data.get("source_location", None), SourceLocation | None
                        ),
                    )
                case _:
                    return make_dict_structure_fn(
                        wtype,
                        converter,
                    )(data_with_optional_fields, wtype)

            return wtype(**data)
            #
            # return make_dict_structure_fn(
            #     wtype,
            #     converter,
            # )(data_with_optional_fields, wtype)
        else:
            return make_dict_structure_fn(cls, converter)(data, cls)

    return structure_func


def structure_str_or_int(data: typing.Any, _: type) -> typing.Any:
    match data:
        case str(str_value):
            return str_value
        case int(int_value):
            return int_value
    raise ValueError(f"{data!r} is neither string nor int")


def structure_stable_set(data: typing.Any, _: type) -> typing.Any:
    match data:
        case [*elements] if all(isinstance(i, int) for i in elements):
            return StableSet(*elements)
    raise ValueError(f"{data!r} is not a supported stable set type")


def issubclass_safe(sub: typing.Any, sup: type) -> bool:
    if typing.get_origin(sub) is not None and issubclass_safe(typing.get_origin(sub), sup):
        # is an instantiation of a generic type, so compare also the unparameterized type
        return True
    # check if sub is actually a class, otherwise issubclass throws
    return inspect.isclass(sub) and issubclass(sub, sup)


def configure_cattrs() -> Converter:
    converter = Converter()

    converter.register_structure_hook(str | int, structure_str_or_int)

    converter.register_structure_hook_func(
        lambda t: issubclass_safe(t, awst_nodes.Node),
        build_node_structure_func(converter),
    )
    converter.register_structure_hook_func(
        lambda t: issubclass_safe(t, wtypes.WType),
        build_wtype_structure_func(converter),
    )

    converter.register_structure_hook_func(
        lambda t: issubclass_safe(t, StableSet), structure_stable_set
    )

    converter.register_structure_hook_func(
        lambda t: issubclass_safe(t, immutabledict), lambda o, t: immutabledict(o)
    )

    configure_tagged_union(awst_nodes.Lvalue, converter)

    configure_tagged_union(awst_nodes.StorageExpression, converter)

    return converter
