import attrs

from puya.codegen.callgraph import CallGraph
from puya.context import CompileContext
from puya.ir import models as ir


@attrs.frozen
class ProgramCodeGenContext(CompileContext):
    contract: ir.Contract
    program: ir.Program
    call_graph: CallGraph
