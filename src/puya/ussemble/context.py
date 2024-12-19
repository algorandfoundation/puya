import typing
from collections.abc import Mapping
from functools import cached_property

import attrs

from puya.arc56_models import AVMType
from puya.context import CompileContext
from puya.models import ProgramReference, TemplateValue


@attrs.frozen(kw_only=True)
class AssembleContext(CompileContext):
    program_ref: ProgramReference
    is_reference: bool
    template_variable_types: Mapping[str, typing.Literal[AVMType.uint64, AVMType.bytes]]
    """Template variables that are required and their types"""
    template_constants: Mapping[str, TemplateValue] | None
    """Template variables provided via compilation"""

    @cached_property
    def provided_template_variables(self) -> Mapping[str, TemplateValue]:
        return {
            **{k: (v, None) for k, v in self.options.template_variables.items()},
            **(self.template_constants or {}),
        }

    @cached_property
    def offset_pc_from_constant_blocks(self) -> bool:
        # only need to offset PC if there are any unspecified template variables
        return not (self.provided_template_variables.keys() >= self.template_variable_types.keys())
