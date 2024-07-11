import typing
from collections.abc import Mapping

import attrs
from immutabledict import immutabledict

from puya.context import CompileContext
from puya.models import ContractReference, LogicSigReference, StateTotals, TemplateValue


class ProgramBytecodeProtocol(typing.Protocol):
    def __call__(
        self,
        ref: ContractReference | LogicSigReference,
        kind: typing.Literal["approval", "clear_state", "logic_sig"],
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes: ...


@attrs.frozen
class IROptimizeContext(CompileContext):
    get_program_bytecode: ProgramBytecodeProtocol
    state_totals: Mapping[ContractReference, StateTotals]
