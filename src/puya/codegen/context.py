import attrs

from puya.context import CompileContext
from puya.ir import models as ir


@attrs.frozen
class ProgramCodeGenContext(CompileContext):
    contract: ir.Contract
    program: ir.Program
