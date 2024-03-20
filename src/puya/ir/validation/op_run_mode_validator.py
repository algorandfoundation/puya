import typing

from puya import log
from puya.ir.avm_ops_models import RunMode
from puya.ir.models import Contract, Intrinsic, LogicSignature, ModuleArtifact
from puya.ir.visitor import IRTraverser

logger = log.get_logger(__name__)


class OpRunModeValidator(IRTraverser):
    def __init__(self, run_mode: typing.Literal[RunMode.app, RunMode.lsig]) -> None:
        self._current_run_mode = run_mode

    @classmethod
    def validate(cls, artifact: ModuleArtifact) -> None:
        match artifact:
            case LogicSignature() as l_sig:
                cls.validate_logic_sig(l_sig)
            case Contract() as contract:
                cls.validate_contract(contract)
            case _:
                typing.assert_never(artifact)

    @classmethod
    def validate_logic_sig(cls, logic_sig: LogicSignature) -> None:
        validator = cls(RunMode.lsig)
        for sub in logic_sig.program.all_subroutines:
            validator.visit_all_blocks(sub.body)

    @classmethod
    def validate_contract(cls, contract: Contract) -> None:
        validator = cls(RunMode.app)
        subs = (sub for program in contract.all_programs() for sub in program.all_subroutines)
        for sub in subs:
            validator.visit_all_blocks(sub.body)

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        match intrinsic.op_variant.supported_modes:
            case RunMode.any:
                pass
            case RunMode.app:
                if self._current_run_mode != RunMode.app:
                    logger.warning(
                        f"The operation {intrinsic} is only allowed in smart contracts",
                        location=intrinsic.source_location,
                    )
            case RunMode.lsig:
                if self._current_run_mode != RunMode.lsig:
                    logger.warning(
                        f"The operation {intrinsic} is only allowed in logic signatures",
                        location=intrinsic.source_location,
                    )
            case _:
                typing.assert_never(intrinsic.op_variant.supported_modes)
