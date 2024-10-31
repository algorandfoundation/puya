import abc
import typing

from puya.context import CompileContext
from puya.ir.avm_ops_models import RunMode
from puya.ir.models import Contract, LogicSignature, ModuleArtifact, Program
from puya.ir.visitor import IRTraverser


class DestructuredIRValidator(IRTraverser, abc.ABC):
    def __init__(
        self,
        context: CompileContext,
        program: Program,
        run_mode: typing.Literal[RunMode.app, RunMode.lsig],
    ):
        self.context = context
        self.current_run_mode = run_mode
        self.active_program = program

    @classmethod
    def validate(cls, context: CompileContext, artifact: ModuleArtifact) -> None:
        match artifact:
            case LogicSignature() as l_sig:
                cls.validate_logic_sig(context, l_sig)
            case Contract() as contract:
                cls.validate_contract(context, contract)
            case _:
                typing.assert_never(artifact)

    @classmethod
    def validate_logic_sig(cls, context: CompileContext, logic_sig: LogicSignature) -> None:
        validator = cls(context, logic_sig.program, RunMode.lsig)
        for sub in logic_sig.program.all_subroutines:
            validator.visit_all_blocks(sub.body)

    @classmethod
    def validate_contract(cls, context: CompileContext, contract: Contract) -> None:
        for program in contract.all_programs():
            validator = cls(context, program, RunMode.app)
            for sub in program.all_subroutines:
                validator.visit_all_blocks(sub.body)
