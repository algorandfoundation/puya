import abc

import attrs

from puyapy.awst_build import pytypes
from puyapy.fast import nodes as fast_nodes
from puyapy.models import ConstantValue


@attrs.frozen(kw_only=True)
class Symbol(abc.ABC):
    @property
    @abc.abstractmethod
    def definition(self) -> fast_nodes.Statement: ...


@attrs.frozen(kw_only=True)
class ResolvedSymbol(Symbol, abc.ABC):
    qualified_name: str


@attrs.frozen(kw_only=True)
class ImportedModule(ResolvedSymbol):
    definition: fast_nodes.AnyImport
    type_checking_only: bool


@attrs.frozen(kw_only=True)
class StubReference(ResolvedSymbol):
    definition: fast_nodes.Statement


@attrs.frozen(kw_only=True)
class Const(ResolvedSymbol):
    definition: fast_nodes.Assign | fast_nodes.MultiAssign
    value: ConstantValue


@attrs.frozen(kw_only=True)
class Subroutine(ResolvedSymbol):
    definition: fast_nodes.FunctionDef


@attrs.frozen(kw_only=True)
class LogicSig(ResolvedSymbol):
    definition: fast_nodes.FunctionDef


@attrs.frozen(kw_only=True)
class DataClass(ResolvedSymbol):
    definition: fast_nodes.ClassDef
    pytype: pytypes.NamedTupleType | pytypes.StructType


@attrs.frozen(kw_only=True)
class ContractClass(ResolvedSymbol):
    definition: fast_nodes.ClassDef
    pytype: pytypes.ContractType


CodeSymbol = Subroutine | LogicSig | ContractClass


@attrs.frozen(kw_only=True)
class TypedClientClass(ResolvedSymbol):
    definition: fast_nodes.ClassDef
    pytype: pytypes.StaticType


@attrs.frozen(kw_only=True)
class TypeAlias(ResolvedSymbol):
    definition: fast_nodes.Assign
    resolved_type: pytypes.PyType


@attrs.frozen(kw_only=True)
class DeferredTypeCheckingFromImport(Symbol):
    definition: fast_nodes.FromImport


@attrs.frozen(kw_only=True)
class DeferredDataClass(Symbol):
    definition: fast_nodes.ClassDef


@attrs.frozen(kw_only=True)
class DeferredTypeAlias(Symbol):
    definition: fast_nodes.Assign
