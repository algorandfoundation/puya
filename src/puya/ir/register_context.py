import abc
from collections.abc import Sequence

from puya.ir._puya_lib import PuyaLibIR
from puya.ir.models import Op, Register, Subroutine, Value, ValueProvider
from puya.ir.types_ import IRType
from puya.parse import SourceLocation


class IRRegisterContext(abc.ABC):
    @abc.abstractmethod
    def next_tmp_name(self, description: str) -> str: ...

    @abc.abstractmethod
    def new_register(
        self, name: str, ir_type: IRType, location: SourceLocation | None
    ) -> Register: ...

    @abc.abstractmethod
    def add_assignment(
        self, targets: list[Register], source: ValueProvider, loc: SourceLocation | None
    ) -> None: ...

    @abc.abstractmethod
    def add_op(self, op: Op) -> None: ...

    @abc.abstractmethod
    def resolve_embedded_func(self, full_name: PuyaLibIR) -> Subroutine: ...

    @abc.abstractmethod
    def materialise_value_provider(
        self, provider: ValueProvider, description: str | Sequence[str]
    ) -> list[Value]: ...
