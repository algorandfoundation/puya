from algopy import ARC4Contract, Txn, UInt64, arc4, logicsig, op


@logicsig(avm_version=11)
def avm_11_sig() -> UInt64:
    return op.sumhash512(b"").length


class Contract(ARC4Contract, avm_version=11):
    @arc4.abimethod
    def test_new_ops(self) -> None:
        # op functions
        assert not op.falcon_verify(b"", b"", op.bzero(1793))
        assert op.sumhash512(b"")
        assert op.online_stake()

        # AcctParamsGet, TODO: add to Account once 11 is in mainnet?
        a, b = op.AcctParamsGet.acct_incentive_eligible(Txn.sender)
        c, d = op.AcctParamsGet.acct_last_proposed(Txn.sender)
        e, f = op.AcctParamsGet.acct_last_heartbeat(Txn.sender)

        # Block
        assert not op.Block.blk_proposer(0), "proposer"
        assert op.Block.blk_fees_collected(0), "fees collected"
        assert op.Block.blk_bonus(0), "bonus"
        assert op.Block.blk_branch(0), "branch"
        assert op.Block.blk_fee_sink(0), "fee sink"
        assert op.Block.blk_protocol(0), "protocol"
        assert op.Block.blk_txn_counter(0), "txn counter"
        assert op.Block.blk_proposer_payout(0), "proposer payout"

        # Global
        assert op.Global.payouts_enabled, "payouts_enabled"
        assert op.Global.payouts_go_online_fee, "payouts_go_online_fee"
        assert op.Global.payouts_percent, "payouts_percent"
        assert op.Global.payouts_min_balance, "payouts_min_balance"
        assert op.Global.payouts_max_balance, "payouts_max_balance"

        # Voter params
        g, h = op.VoterParamsGet.voter_balance(0)
        i, j = op.VoterParamsGet.voter_incentive_eligible(0)
