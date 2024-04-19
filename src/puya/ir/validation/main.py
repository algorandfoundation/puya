import attrs

from puya.context import CompileContext
from puya.ir.models import ModuleArtifact
from puya.ir.validation.itxn_result_field_validator import ITxnResultFieldValidator
from puya.ir.validation.min_avm_version_validator import MinAvmVersionValidator
from puya.ir.validation.op_run_mode_validator import OpRunModeValidator


def validate_module_artifact(context: CompileContext, artifact: ModuleArtifact) -> None:
    attrs.validate(artifact)
    for validator_cls in (
        OpRunModeValidator,
        MinAvmVersionValidator,
        ITxnResultFieldValidator,
    ):
        validator_cls.validate(context, artifact)
