from puya.errors import InternalError
from puya.ussemble import models
from puya.ussemble._utils import get_label_indexes


def validate_labels(avm_ops: list[models.Node]) -> None:
    label_indexes = get_label_indexes(avm_ops)
    for op in avm_ops:
        match op:
            case models.Jump(label=label):
                labels = [label]
            case models.MultiJump(labels=labels):
                pass
            case _:
                continue
        for label in labels:
            try:
                label_indexes[label]
            except KeyError as ex:
                raise InternalError(f"Label not found: {label.name}") from ex
