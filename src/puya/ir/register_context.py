import abc

from puya.ir.models import Op, Register, ValueProvider
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
