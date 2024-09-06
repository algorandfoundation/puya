from collections.abc import Mapping, Sequence

import attrs


@attrs.frozen
class FunctionDebug:
    full_name: str
    """Fully qualified HLL name"""
    subroutine_label: str
    """Label for subroutine entrypoint in TEAL"""
    params: Mapping[str, str]
    """Mapping of parameter name to type"""
    returns: Sequence[str]
    """types returned"""


@attrs.frozen
class DebugInfo:
    _function_debug: dict[tuple[str, str], FunctionDebug] = attrs.field(factory=dict, init=False)

    @property
    def function_debug(self) -> Mapping[tuple[str, str], FunctionDebug]:
        return self._function_debug

    def add_function(
        self,
        program_id: str,
        full_name: str,
        subroutine_label: str,
        params: Mapping[str, str],
        returns: Sequence[str],
    ) -> None:
        self._function_debug[(program_id, subroutine_label)] = FunctionDebug(
            full_name=full_name,
            subroutine_label=subroutine_label,
            params=params,
            returns=returns,
        )
