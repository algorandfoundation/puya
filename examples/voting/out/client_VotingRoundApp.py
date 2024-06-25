# This file is auto-generated, do not modify
# flake8: noqa
# fmt: off
import typing

import algopy

class VotingPreconditions(algopy.arc4.Struct):
    is_voting_open: algopy.arc4.UIntN[typing.Literal[64]]
    is_allowed_to_vote: algopy.arc4.UIntN[typing.Literal[64]]
    has_already_voted: algopy.arc4.UIntN[typing.Literal[64]]
    current_time: algopy.arc4.UIntN[typing.Literal[64]]

class VotingRoundApp(algopy.arc4.ARC4Client, typing.Protocol):
    @algopy.arc4.abimethod(create='require')
    def create(
        self,
        vote_id: algopy.arc4.String,
        snapshot_public_key: algopy.arc4.DynamicBytes,
        metadata_ipfs_cid: algopy.arc4.String,
        start_time: algopy.arc4.UIntN[typing.Literal[64]],
        end_time: algopy.arc4.UIntN[typing.Literal[64]],
        option_counts: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[8]]],
        quorum: algopy.arc4.UIntN[typing.Literal[64]],
        nft_image_url: algopy.arc4.String,
    ) -> None: ...

    @algopy.arc4.abimethod
    def bootstrap(
        self,
        fund_min_bal_req: algopy.gtxn.PaymentTransaction,
    ) -> None: ...

    @algopy.arc4.abimethod
    def close(
        self,
    ) -> None: ...

    @algopy.arc4.abimethod(readonly=True)
    def get_preconditions(
        self,
        signature: algopy.arc4.DynamicBytes,
    ) -> VotingPreconditions: ...

    @algopy.arc4.abimethod
    def vote(
        self,
        fund_min_bal_req: algopy.gtxn.PaymentTransaction,
        signature: algopy.arc4.DynamicBytes,
        answer_ids: algopy.arc4.DynamicArray[algopy.arc4.UIntN[typing.Literal[8]]],
    ) -> None: ...
