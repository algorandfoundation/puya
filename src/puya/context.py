import typing
from collections.abc import Mapping, Sequence
from pathlib import Path

import attrs
from immutabledict import immutabledict

from puya import log
from puya.artifact_metadata import StateTotals
from puya.compilation_artifacts import TemplateValue
from puya.options import PuyaOptions
from puya.parse import SourceLocation
from puya.program_refs import ContractReference, LogicSigReference, ProgramKind

logger = log.get_logger(__name__)


@attrs.define(kw_only=True)
class CompileContext:
    options: PuyaOptions
    compilation_set: Mapping[ContractReference | LogicSigReference, Path]
    sources_by_path: Mapping[Path, Sequence[str] | None]

    def try_get_source(self, location: SourceLocation | None) -> Sequence[str] | None:
        return try_get_source(self.sources_by_path, location)


def try_get_source(
    sources_by_path: Mapping[Path, Sequence[str] | None], location: SourceLocation | None
) -> Sequence[str] | None:
    if not location or not location.file:
        return None
    source_lines = sources_by_path.get(location.file)
    if source_lines is None:
        return None

    src_content = list(source_lines[location.line - 1 : location.end_line])
    if not src_content:
        logger.warning(f"could not locate source: {location}", location=None)
    else:
        end_column = location.end_column
        if end_column is not None:
            src_content[-1] = src_content[-1][:end_column]
        start_column = location.column
        if start_column is not None:
            src_content[0] = src_content[0][start_column:]
    return src_content


class CompiledProgramProvider(typing.Protocol):
    def build_program_bytecode(
        self,
        ref: ContractReference | LogicSigReference,
        kind: ProgramKind,
        *,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes: ...

    def get_state_totals(self, ref: ContractReference) -> StateTotals: ...


class OutputPathProvider(typing.Protocol):
    def begin_group(self) -> None: ...
    def next_path(self, *, kind: str, qualifier: str, suffix: str) -> Path: ...


@attrs.define(kw_only=True)
class ArtifactCompileContext(CompileContext):
    _compiled_program_provider: CompiledProgramProvider = attrs.field(
        on_setattr=attrs.setters.frozen
    )
    _output_path_provider: OutputPathProvider | None = attrs.field(on_setattr=attrs.setters.frozen)

    def begin_output_group(self) -> None:
        if self._output_path_provider is not None:
            self._output_path_provider.begin_group()

    def build_output_path(self, kind: str, qualifier: str, suffix: str) -> Path | None:
        if self._output_path_provider is None:
            return None
        return self._output_path_provider.next_path(kind=kind, qualifier=qualifier, suffix=suffix)

    @typing.overload
    def build_program_bytecode(
        self,
        ref: ContractReference,
        kind: typing.Literal[ProgramKind.approval, ProgramKind.clear_state],
        *,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes: ...

    @typing.overload
    def build_program_bytecode(
        self,
        ref: LogicSigReference,
        kind: typing.Literal[ProgramKind.logic_signature],
        *,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes: ...

    def build_program_bytecode(
        self,
        ref: ContractReference | LogicSigReference,
        kind: ProgramKind,
        *,
        template_constants: immutabledict[str, TemplateValue],
    ) -> bytes:
        return self._compiled_program_provider.build_program_bytecode(
            ref, kind, template_constants=template_constants
        )

    def get_state_totals(self, ref: ContractReference) -> StateTotals:
        return self._compiled_program_provider.get_state_totals(ref)
