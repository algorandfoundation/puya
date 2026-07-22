from algopy import ARC4Contract, Bytes, Global, UInt64, arc4, logicsig, op


@logicsig(avm_version=13)
def avm_13_sig() -> UInt64:
    assert op.sha512(b"") != op.sha512(b"a")
    scalar = op.bzero(32)
    bn = op.poseidon2(op.Poseidon2Configurations.BN254t2, scalar)
    bls = op.poseidon2(op.Poseidon2Configurations.BLS12_381t2, scalar)
    assert bn != bls
    return bn.length


class Contract(ARC4Contract, avm_version=13):
    @arc4.abimethod
    def test_new_ops(self) -> None:
        assert op.sha512(b"") != op.sha512(b"a")

    @arc4.abimethod
    def test_poseidon2(self) -> None:
        scalar = op.bzero(32)
        bn = op.poseidon2(op.Poseidon2Configurations.BN254t2, scalar)
        bls = op.poseidon2(op.Poseidon2Configurations.BLS12_381t2, scalar)
        assert bn.length == 32
        assert bls.length == 32
        assert bn != bls

    @arc4.abimethod
    def test_app_params(self) -> None:
        app = Global.current_application_id
        sponsor, exists = op.AppParamsGet.app_size_sponsor(app)
        assert exists
        assert sponsor == Global.zero_address
        fbr, exists = op.AppParamsGet.app_foreign_box_reads(app)
        assert exists
        assert not fbr
        fba, exists = op.AppParamsGet.app_family_box_access(app)
        assert exists
        assert not fba
        op.AppParamsSet.app_foreign_box_reads(True)
        op.AppParamsSet.app_family_box_access(True)
        fbr, exists = op.AppParamsGet.app_foreign_box_reads(app)
        assert exists
        assert fbr
        fba, exists = op.AppParamsGet.app_family_box_access(app)
        assert exists
        assert fba

    @arc4.abimethod
    def test_app_box_ops(self) -> None:
        app = Global.current_application_id
        name = Bytes(b"bx")
        assert op.AppBox.create(app, name, 8)
        op.AppBox.put(app, name, op.bzero(8))
        value, exists = op.AppBox.get(app, name)
        assert exists
        assert value == op.bzero(8)
        op.AppBox.replace(app, name, 0, b"\xff")
        assert op.AppBox.extract(app, name, 0, 1) == b"\xff"
        op.AppBox.splice(app, name, 1, 3, b"abc")
        op.AppBox.resize(app, name, 4)
        length, exists = op.AppBox.length(app, name)
        assert exists
        assert length == 4
        assert op.AppBox.delete(app, name)

    @arc4.abimethod
    def test_block(self) -> None:
        branch512 = op.Block.blk_branch512(0)
        sha512_256_commitment = op.Block.blk_sha512_256_txn_commitment(0)
        sha256_commitment = op.Block.blk_sha256_txn_commitment(0)
        sha512_commitment = op.Block.blk_sha512_txn_commitment(0)
        assert branch512 != sha512_commitment
        assert sha512_256_commitment != sha256_commitment
