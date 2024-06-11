import attrs

from puya.context import CompileContext


@attrs.frozen(kw_only=True)
class AssembleContext(CompileContext):
    template_variables: dict[str, int | bytes] = attrs.field(factory=dict)
