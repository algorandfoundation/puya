from __future__ import annotations  # needed to break import cycle

import abc
import typing

if typing.TYPE_CHECKING:
    from puyapy.fast import nodes


class StatementVisitor[T](abc.ABC):
    @abc.abstractmethod
    def visit_function_def(self, fdef: nodes.FunctionDef) -> T: ...
