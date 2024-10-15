from collections.abc import Mapping

import attrs

from puya.context import CompileContext
from puya.models import TemplateValue


@attrs.frozen(kw_only=True)
class AssembleContext(CompileContext):
    mocked_template_variables: dict[str, TemplateValue] = attrs.field(factory=dict)
    """Mocked template variables, used for generating debug info only"""
    provided_template_variables: dict[str, TemplateValue] = attrs.field(factory=dict)
    """Template variables provided via command line, or compilation"""

    @property
    def template_variables(self) -> Mapping[str, TemplateValue]:
        return {
            **self.mocked_template_variables,
            **self.provided_template_variables,
        }

    @property
    def offset_pc_from_constant_blocks(self) -> bool:
        # only need to offset PC if there are any unspecified template variables
        return bool(self.mocked_template_variables)
