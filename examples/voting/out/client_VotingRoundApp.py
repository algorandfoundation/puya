# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import puyapy

class VotingPreconditions(puyapy.arc4.Struct):
    is_voting_open: puyapy.arc4.UInt64
    is_allowed_to_vote: puyapy.arc4.UInt64
    has_already_voted: puyapy.arc4.UInt64
    current_time: puyapy.arc4.UInt64

class VotingRoundApp(puyapy.arc4.ARC4Client, typing.Protocol):
    @puyapy.arc4.abimethod(create=True)
    def create(
        self,
        vote_id: puyapy.arc4.String,
        snapshot_public_key: puyapy.arc4.DynamicBytes,
        metadata_ipfs_cid: puyapy.arc4.String,
        start_time: puyapy.arc4.UInt64,
        end_time: puyapy.arc4.UInt64,
        option_counts: puyapy.arc4.DynamicArray[puyapy.arc4.UInt8],
        quorum: puyapy.arc4.UInt64,
        nft_image_url: puyapy.arc4.String,
    ) -> None: ...

    @puyapy.arc4.abimethod
    def bootstrap(
        self,
        fund_min_bal_req: puyapy.gtxn.PaymentTransaction,
    ) -> None: ...

    @puyapy.arc4.abimethod
    def close(
        self,
    ) -> None: ...

    @puyapy.arc4.abimethod(readonly=True)
    def get_preconditions(
        self,
        signature: puyapy.arc4.DynamicBytes,
    ) -> VotingPreconditions: ...

    @puyapy.arc4.abimethod
    def vote(
        self,
        fund_min_bal_req: puyapy.gtxn.PaymentTransaction,
        signature: puyapy.arc4.DynamicBytes,
        answer_ids: puyapy.arc4.DynamicArray[puyapy.arc4.UInt8],
    ) -> None: ...
