from puya.teal import models


def _simplify_repeated_rotation_ops(
    maybe_simplify: list[models.Cover | models.Uncover],
) -> tuple[list[models.Cover | models.Uncover], bool]:
    first = maybe_simplify[0]
    is_cover = isinstance(first, models.Cover)
    n = first.n
    number_of_ops = len(maybe_simplify)
    number_of_inverse = n + 1 - number_of_ops
    while number_of_inverse < 0:
        number_of_inverse += n + 1
    if number_of_inverse >= number_of_ops:
        return maybe_simplify, False
    inverse_op: models.Cover | models.Uncover = (
        models.Uncover(n=n, source_location=first.source_location)
        if is_cover
        else models.Cover(n=n, source_location=first.source_location)
    )
    return [inverse_op] * number_of_inverse, True


def simplify_repeated_rotation_ops(block: models.TealBlock) -> bool:
    result = list[models.TealOp]()
    maybe_simplify = list[models.Cover | models.Uncover]()
    modified = False
    for op in block.ops:
        if isinstance(op, models.Cover | models.Uncover) and (
            not maybe_simplify or op == maybe_simplify[0]
        ):
            maybe_simplify.append(op)
        else:
            if maybe_simplify:
                maybe_simplified, modified_ = _simplify_repeated_rotation_ops(maybe_simplify)
                modified = modified or modified_
                result.extend(maybe_simplified)
                maybe_simplify = []
            result.append(op)
    if maybe_simplify:
        result.extend(maybe_simplify)
    block.ops = result
    return modified
