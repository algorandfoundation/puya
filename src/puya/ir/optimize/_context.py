import attrs

from puya.context import ArtifactCompileContext


@attrs.define
class IROptimizationContext(ArtifactCompileContext):
    inlineable_calls: set[tuple[str, str]] = attrs.field(factory=set)
    """src -> dst pairs that can/should be inlined"""
