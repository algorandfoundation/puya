import contextlib
from collections.abc import Iterator

from puya.context import CompileContext
from puya.ir.avm_ops_models import RunMode
from puya.ir.models import Contract, Intrinsic, LogicSignature, ModuleArtifact
from puya.ir.visitor import IRTraverser


class OpRunModeValidator(IRTraverser):
    def __init__(self, context: CompileContext) -> None:
        self.context = context
        self._current_run_mode_name: str
        self._current_run_mode = RunMode.any

    @staticmethod
    def validate(context: CompileContext, artifact: ModuleArtifact) -> None:
        validator = OpRunModeValidator(context)

        match artifact:
            case LogicSignature() as l_sig:
                validator.validate_logic_sig(l_sig)
            case Contract() as contract:
                validator.validate_contract(contract)

    def validate_logic_sig(self, logic_sig: LogicSignature) -> None:
        with self._enter_run_mode(RunMode.lsig):
            for sub in logic_sig.program.all_subroutines:
                self.visit_all_blocks(sub.body)

    def validate_contract(self, contract: Contract) -> None:
        with self._enter_run_mode(RunMode.app):
            subs = (sub for program in contract.all_programs() for sub in program.all_subroutines)
            for sub in subs:
                self.visit_all_blocks(sub.body)

    @contextlib.contextmanager
    def _enter_run_mode(self, run_mode: RunMode) -> Iterator[None]:
        self._current_run_mode = run_mode
        try:
            yield
        finally:
            self._current_run_mode = RunMode.any

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        if self._current_run_mode == RunMode.any:
            return
        match intrinsic.op_variant.supported_modes:
            case RunMode.any:
                pass
            case RunMode.app if self._current_run_mode != RunMode.app:
                self.context.errors.warning(
                    f"The operation {intrinsic} is only allowed in smart contracts",
                    intrinsic.source_location,
                )
            case RunMode.lsig if self._current_run_mode != RunMode.lsig:
                self.context.errors.warning(
                    f"The operation {intrinsic} is only allowed in logic signatures",
                    intrinsic.source_location,
                )
