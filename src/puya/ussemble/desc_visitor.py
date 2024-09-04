from puya.ussemble import models
from puya.ussemble.debug import _bytes_desc
from puya.ussemble.visitor import AVMVisitor


class OpDescription(AVMVisitor[str]):
    def visit_int_block(self, block: models.IntBlock) -> str:
        return f"{block.op_code} {' '.join(map(str, block.constants))}"

    def visit_bytes_block(self, block: models.BytesBlock) -> str:
        return f"{block.op_code} {' '.join(map(_bytes_desc, block.constants))}"

    def visit_intc(self, load: models.IntC) -> str:
        return f"{load.op_code} {load.index}"

    def visit_bytesc(self, load: models.BytesC) -> str:
        return f"{load.op_code} {load.index}"

    def visit_push_int(self, load: models.PushInt) -> str:
        return f"{load.op_code} {load.value}"

    def visit_push_ints(self, load: models.PushInts) -> str:
        return f"{load.op_code} {' '.join(map(str, load.values))}"

    def visit_push_bytes(self, load: models.PushBytes) -> str:
        return f"{load.op_code} {_bytes_desc(load.value)}"

    def visit_push_bytess(self, load: models.PushBytess) -> str:
        return f"{load.op_code} {' '.join(map(_bytes_desc, load.values))}"

    def visit_jump(self, jump: models.Jump) -> str:
        return f"{jump.op_code} {jump.label.name}"

    def visit_multi_jump(self, jump: models.MultiJump) -> str:
        return f"{jump.op_code} {' '.join([label.name for label in jump.labels])}"

    def visit_label(self, jump: models.Label) -> str:
        return f"{jump.name}:"

    def visit_intrinsic(self, intrinsic: models.Intrinsic) -> str:
        return f"{intrinsic.op_code} {' '.join(map(str, intrinsic.immediates))}".rstrip()
