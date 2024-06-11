from puya.ussemble import models


def get_label_indexes(avm_ops: list[models.Node]) -> dict[models.Label, int]:
    return {node: index for index, node in enumerate(avm_ops) if isinstance(node, models.Label)}
