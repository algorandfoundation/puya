import attrs

from wyvern.codegen.callgraph import CallGraph
from wyvern.context import CompileContext
from wyvern.ir import models as ir


@attrs.frozen
class ProgramCodeGenContext(CompileContext):
    contract: ir.Contract
    program: ir.Program
    call_graph: CallGraph
