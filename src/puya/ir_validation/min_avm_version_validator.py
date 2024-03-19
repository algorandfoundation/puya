from puya.context import CompileContext
from puya.ir.models import Contract, Intrinsic, LogicSignature, ModuleArtifact
from puya.ir.visitor import IRTraverser


class MinAvmVersionValidator(IRTraverser):
    def __init__(self, context: CompileContext) -> None:
        self.context = context

    @staticmethod
    def validate(context: CompileContext, artifact: ModuleArtifact) -> None:
        validator = MinAvmVersionValidator(context)

        match artifact:
            case LogicSignature() as l_sig:
                validator.validate_logic_sig(l_sig)
            case Contract() as contract:
                validator.validate_contract(contract)

    def validate_logic_sig(self, logic_sig: LogicSignature) -> None:
        for sub in logic_sig.program.all_subroutines:
            self.visit_all_blocks(sub.body)

    def validate_contract(self, contract: Contract) -> None:
        subs = (sub for program in contract.all_programs() for sub in program.all_subroutines)
        for sub in subs:
            self.visit_all_blocks(sub.body)

    def visit_intrinsic_op(self, intrinsic: Intrinsic) -> None:
        if intrinsic.op.min_avm_version > self.context.options.target_avm_version:
            self.context.errors.warning(
                f"Opcode {intrinsic.op} requires a min avm version of "
                f"{intrinsic.op.min_avm_version} but the target avm version is"
                f" {self.context.options.target_avm_version}",
                intrinsic.source_location,
            )
