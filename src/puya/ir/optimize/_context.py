import attrs

from puya.context import ArtifactCompileContext


@attrs.define
class IROptimizationContext(ArtifactCompileContext):
    pass


@attrs.define(kw_only=True)
class IROptimizationPassContext(IROptimizationContext):
    pass_number: int
    inlineable_calls: set[tuple[str, str]] = attrs.field(factory=set)
    """src -> dst pairs that can/should be inlined"""
    constant_with_constant_args: dict[str, bool] = attrs.field(factory=dict)
