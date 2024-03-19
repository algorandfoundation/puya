from puya.context import CompileContext
from puya.ir.models import ModuleArtifact
from puya.ir_validation.min_avm_version_validator import MinAvmVersionValidator
from puya.ir_validation.op_run_mode_validator import OpRunModeValidator


def validate_module_artifact(context: CompileContext, artifact: ModuleArtifact) -> None:
    OpRunModeValidator.validate(context, artifact)
    MinAvmVersionValidator.validate(context, artifact)
