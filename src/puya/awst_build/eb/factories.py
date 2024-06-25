from puya.awst.nodes import Expression
from puya.awst_build import pytypes
from puya.awst_build.eb.interface import CallableBuilder, InstanceBuilder
from puya.parse import SourceLocation


def builder_for_instance(pytyp: pytypes.PyType, expr: Expression) -> InstanceBuilder:
    from puya.awst_build.eb import _type_registry

    return _type_registry.builder_for_instance(pytyp, expr)


def builder_for_type(pytyp: pytypes.PyType, expr_loc: SourceLocation) -> CallableBuilder:
    from puya.awst_build.eb import _type_registry

    return _type_registry.builder_for_type(pytyp, expr_loc)


def try_get_builder_for_func(fullname: str, expr_loc: SourceLocation) -> CallableBuilder | None:
    from puya.awst_build.eb import _type_registry

    builder = _type_registry.FUNC_NAME_TO_BUILDER.get(fullname)
    if builder is not None:
        return builder(expr_loc)
    return None
