from puya.errors import InternalError
from puya.ir import models


def get_definition(
    subroutine: models.Subroutine, register: models.Register, *, should_exist: bool = True
) -> models.Assignment | models.Phi | None:
    if register in subroutine.parameters:
        return None
    for block in subroutine.body:
        for phi in block.phis:
            if phi.register == register:
                return phi
        for op in block.ops:
            if isinstance(op, models.Assignment) and register in op.targets:
                return op
    if should_exist:
        raise InternalError(f"Register is not defined: {register}", subroutine.source_location)
    return None
