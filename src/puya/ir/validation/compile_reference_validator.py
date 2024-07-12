import typing
from collections.abc import Iterable

from puya import log
from puya.ir.models import (
    CompiledContractReference,
    CompiledLogicSigReference,
    Constant,
    TemplateVar,
    Value,
)
from puya.ir.validation._base import DestructuredIRValidator

logger = log.get_logger(__name__)


class CompileReferenceValidator(DestructuredIRValidator):
    @typing.override
    def visit_compiled_contract_reference(self, const: CompiledContractReference) -> None:
        _log_non_constant_values(const.template_variables.values())

    @typing.override
    def visit_compiled_logicsig_reference(self, const: CompiledLogicSigReference) -> None:
        _log_non_constant_values(const.template_variables.values())


def _log_non_constant_values(values: Iterable[Value]) -> None:
    for value in values:
        if isinstance(value, Constant):
            continue
        if isinstance(value, TemplateVar):
            logger.error(
                "nested template variables are not supported",
                location=value.source_location,
            )
        else:
            logger.error(
                "non-constant template value",
                location=value.source_location,
            )
