import abc
import enum
import typing

import attrs


class ContractReference(str):  # can't use typing.NewType with pattern matching
    __slots__ = ()


class LogicSigReference(str):  # can't use typing.NewType with pattern matching
    __slots__ = ()


class ProgramKind(enum.StrEnum):
    approval = "approval"
    clear_state = "clear"
    logic_signature = "lsig"


class ProgramReference(abc.ABC):
    @property
    @abc.abstractmethod
    def kind(self) -> ProgramKind: ...

    @property
    @abc.abstractmethod
    def reference(self) -> ContractReference | LogicSigReference: ...

    @property
    @abc.abstractmethod
    def id(self) -> str: ...


@attrs.frozen
class LogicSigProgramReference(ProgramReference):
    kind: typing.Literal[ProgramKind.logic_signature] = attrs.field(
        default=ProgramKind.logic_signature, init=False
    )
    reference: LogicSigReference

    @property
    def id(self) -> str:
        return self.reference


@attrs.frozen
class ContractProgramReference(ProgramReference):
    kind: typing.Literal[ProgramKind.approval, ProgramKind.clear_state]
    reference: ContractReference
    program_name: str

    @property
    def id(self) -> str:
        return f"{self.reference}.{self.program_name}"
