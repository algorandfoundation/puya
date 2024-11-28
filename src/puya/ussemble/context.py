import typing
from collections.abc import Mapping
from functools import cached_property

import attrs

from puya.arc56_models import AVMType
from puya.context import CompileContext
from puya.models import TemplateValue


@attrs.frozen(kw_only=True)
class AssembleContext(CompileContext):
    debug_only: bool
    template_variable_types: Mapping[str, typing.Literal[AVMType.uint64, AVMType.bytes]]
    """Template variables that are required and their types"""
    provided_template_variables: Mapping[str, TemplateValue]
    """Template variables provided via command line, or compilation"""

    @cached_property
    def offset_pc_from_constant_blocks(self) -> bool:
        # only need to offset PC if there are any unspecified template variables
        return self.debug_only and not (
            self.provided_template_variables.keys() >= self.template_variable_types.keys()
        )
