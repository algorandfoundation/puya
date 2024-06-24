from __future__ import annotations

import typing

_T = typing.TypeVar("_T")


class TemplateVarGeneric:
    def __getitem__(self, type_: type[_T]) -> typing.Callable[[str], typing.Any]:
        from algopy_testing.context import get_test_context

        context = get_test_context()

        def create_template_var(variable_name: str) -> typing.Any:
            if variable_name not in context._template_vars:
                raise ValueError(f"Template variable {variable_name} not found in test context!")
            return context._template_vars[variable_name]

        return create_template_var


TemplateVar: TemplateVarGeneric = TemplateVarGeneric()
"""Template variables can be used to represent a placeholder for a deploy-time provided value."""
