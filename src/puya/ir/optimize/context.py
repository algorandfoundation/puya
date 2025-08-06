from collections.abc import Mapping

import attrs

from puya.context import ArtifactCompileContext
from puya.ir import models
from puya.ir._puya_lib import PuyaLibIR


@attrs.define(kw_only=True)
class IROptimizationContext(ArtifactCompileContext):
    expand_all_bytes: bool

    inlineable_calls: set[tuple[models.SubroutineID, models.SubroutineID]] = attrs.field(
        factory=set
    )
    """src -> dst pairs that can/should be inlined"""
    constant_with_constant_args: dict[models.SubroutineID, bool] = attrs.field(factory=dict)
    embedded_funcs: Mapping[PuyaLibIR, models.Subroutine]
    maybe_inlineable_subs_by_id: dict[models.SubroutineID, models.Subroutine] | None = None
