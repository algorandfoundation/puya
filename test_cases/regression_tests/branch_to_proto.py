from algopy import ARC4Contract, Bytes, OpUpFeeSource, arc4, ensure_budget, op


class VRFVerifier(ARC4Contract):
    @arc4.abimethod
    def verify(self, message: Bytes, proof: Bytes, pk: Bytes) -> tuple[Bytes, bool]:
        ensure_budget(10_000, OpUpFeeSource.AppAccount)
        return op.vrf_verify(op.VrfVerify.VrfAlgorand, message, proof, pk)
