# Converted from https://github.com/algorandfoundation/nft_voting_tool/blob/c0f8be47ab80c8694d2cf40ca0df54cec07ff14a/src/algorand/smart_contracts/voting.py
import typing

from puyapy import (
    ARC4Contract,
    Bytes,
    Global,
    GlobalState,
    OpUpFeeSource,
    Txn,
    UInt64,
    arc4,
    ensure_budget,
    gtxn,
    itxn,
    log,
    op,
    subroutine,
    uenumerate,
    urange,
)

VoteIndexArray: typing.TypeAlias = arc4.DynamicArray[arc4.UInt8]

VOTE_INDEX_BYTES = 1
VOTE_COUNT_BYTES = 8

# TODO: Do these belong in our stubs?
#: The min balance increase per box created
BOX_FLAT_MIN_BALANCE = 2500

#: The min balance increase per byte of boxes (key included)
BOX_BYTE_MIN_BALANCE = 400

#: The min balance increase for each asset opted into
ASSET_MIN_BALANCE = 100000

TALLY_BOX_KEY = b"V"


class VotingPreconditions(arc4.Struct):
    is_voting_open: arc4.UInt64
    is_allowed_to_vote: arc4.UInt64
    has_already_voted: arc4.UInt64
    current_time: arc4.UInt64


class VotingRoundApp(ARC4Contract):
    def __init__(self) -> None:
        self.is_bootstrapped = False
        # The minimum number of voters who have voted
        self.voter_count = UInt64(0)
        self.close_time = GlobalState(UInt64)

    @arc4.abimethod(create=True)
    def create(
        self,
        vote_id: arc4.String,
        snapshot_public_key: Bytes,
        metadata_ipfs_cid: arc4.String,
        start_time: UInt64,
        end_time: UInt64,
        option_counts: VoteIndexArray,
        quorum: UInt64,
        nft_image_url: arc4.String,
    ) -> None:
        assert start_time < end_time, "End time should be after start time"
        assert end_time >= Global.latest_timestamp, "End time should be in the future"

        self.vote_id = vote_id.decode()
        self.snapshot_public_key = snapshot_public_key
        self.metadata_ipfs_cid = metadata_ipfs_cid.decode()
        self.start_time = start_time
        self.end_time = end_time
        self.quorum = quorum
        self.nft_image_url = nft_image_url.decode()
        self.store_option_counts(option_counts.copy())

    @arc4.abimethod
    def bootstrap(self, fund_min_bal_req: gtxn.PaymentTransaction) -> None:
        assert not self.is_bootstrapped, "Must not be already bootstrapped"
        self.is_bootstrapped = True

        assert (
            fund_min_bal_req.receiver == Global.current_application_address
        ), "Payment must be to app address"

        tally_box_size = self.total_options * VOTE_COUNT_BYTES
        min_balance_req = (
            # minimum balance req for: ALGOs + Vote result NFT asset
            ASSET_MIN_BALANCE * 2
            # create NFT fee
            + 1000
            # tally box
            + BOX_FLAT_MIN_BALANCE
            # tally box key "V"
            + BOX_BYTE_MIN_BALANCE
            # tally box value
            + (tally_box_size * BOX_BYTE_MIN_BALANCE)
        )
        log(min_balance_req)
        assert (
            fund_min_bal_req.amount == min_balance_req
        ), "Payment must be for the exact min balance requirement"
        assert op.Box.create(TALLY_BOX_KEY, tally_box_size)

    @arc4.abimethod
    def close(self) -> None:
        ensure_budget(20000, fee_source=OpUpFeeSource.GroupCredit)
        assert not self.close_time, "Already closed"
        self.close_time.value = Global.latest_timestamp

        note = (
            b'{"standard":"arc69",'
            b'"description":"This is a voting result NFT for voting round with ID '
            + self.vote_id
            + b'.","properties":{"metadata":"ipfs://'
            + self.metadata_ipfs_cid
            + b'","id":"'
            + self.vote_id
            + b'","quorum":'
            + itoa(self.quorum)
            + b',"voterCount":'
            + itoa(self.voter_count)
            + b',"tallies":['
        )

        current_index = UInt64(0)
        for question_index, question_options_arc in uenumerate(self.option_counts):
            if question_index > 0:
                note += b","
            question_options = question_options_arc.decode()
            if question_options > 0:
                note += b"["
                for option_index in urange(question_options):
                    if option_index > 0:
                        note += b","
                    votes_for_option = get_vote_from_box(current_index)
                    note += itoa(votes_for_option)
                    current_index += 1
                note += b"]"
        note += b"]}}"
        self.nft_asset_id = (
            itxn.AssetConfigTransactionParams(
                total=1,
                decimals=0,
                default_frozen=False,
                asset_name=b"[VOTE RESULT] " + self.vote_id,
                unit_name=b"VOTERSLT",
                url=self.nft_image_url,
                note=note,
            )
            .submit()
            .created_asset.asset_id
        )

    @arc4.abimethod(readonly=True)
    def get_preconditions(self, signature: arc4.DynamicBytes) -> VotingPreconditions:
        return VotingPreconditions(
            is_voting_open=arc4.UInt64(self.voting_open()),
            is_allowed_to_vote=arc4.UInt64(self.allowed_to_vote(signature.bytes[2:])),
            has_already_voted=arc4.UInt64(self.already_voted()),
            current_time=arc4.UInt64(Global.latest_timestamp),
        )

    @arc4.abimethod
    def vote(
        self,
        fund_min_bal_req: gtxn.PaymentTransaction,
        signature: Bytes,
        answer_ids: VoteIndexArray,
    ) -> None:
        ensure_budget(7700, fee_source=OpUpFeeSource.GroupCredit)
        # Check voting preconditions
        assert self.allowed_to_vote(signature), "Not allowed to vote"
        assert self.voting_open(), "Voting not open"
        assert not self.already_voted(), "Already voted"
        questions_count = self.option_counts.length
        assert answer_ids.length == questions_count, "Number of answers incorrect"
        # Check voter box is funded
        min_bal_req = BOX_FLAT_MIN_BALANCE + (
            (32 + 2 + VOTE_INDEX_BYTES * answer_ids.length) * BOX_BYTE_MIN_BALANCE
        )
        assert (
            fund_min_bal_req.receiver == Global.current_application_address
        ), "Payment must be to app address"

        log(min_bal_req)
        assert fund_min_bal_req.amount == min_bal_req, "Payment must be the exact min balance"
        # Record the vote for each question
        cumulative_offset = UInt64(0)
        for question_index in urange(questions_count):
            # Load the user's vote for this question
            answer_option_index = answer_ids[question_index].decode()
            options_count = self.option_counts[question_index].decode()
            assert answer_option_index < options_count, "Answer option index invalid"
            increment_vote_in_box(cumulative_offset + answer_option_index)
            cumulative_offset += options_count
            op.Box.put(Txn.sender.bytes, answer_ids.bytes)
            self.voter_count += 1

    @subroutine
    def voting_open(self) -> bool:
        return (
            self.is_bootstrapped
            and not self.close_time
            and self.start_time <= Global.latest_timestamp <= self.end_time
        )

    @subroutine
    def already_voted(self) -> bool:
        (votes, exists) = op.Box.get(Txn.sender.bytes)
        return exists

    @subroutine
    def store_option_counts(self, option_counts: VoteIndexArray) -> None:
        assert option_counts.length, "option_counts should be non-empty"
        assert option_counts.length <= 112, "Can't have more than 112 questions"

        total_options = UInt64(0)
        for item in option_counts:
            total_options += item.decode()
        assert total_options <= 128, "Can't have more than 128 vote options"

        self.option_counts = option_counts.copy()
        self.total_options = total_options

    @subroutine
    def allowed_to_vote(self, signature: Bytes) -> bool:
        ensure_budget(2000)
        return op.ed25519verify_bare(
            Txn.sender.bytes,
            signature,
            self.snapshot_public_key,
        )


@subroutine
def get_vote_from_box(index: UInt64) -> UInt64:
    box_data, exists = op.Box.get(TALLY_BOX_KEY)
    assert exists, "Box not created"
    return op.btoi(op.extract(box_data, index, VOTE_COUNT_BYTES))


@subroutine
def increment_vote_in_box(index: UInt64) -> None:
    box_data, exists = op.Box.get(TALLY_BOX_KEY)
    assert exists, "Box not created"
    current_vote = op.btoi(op.extract(box_data, index, VOTE_COUNT_BYTES))
    op.Box.replace(TALLY_BOX_KEY, index, op.itob(current_vote + 1))


@subroutine
def itoa(i: UInt64) -> Bytes:
    digits = Bytes(b"0123456789")
    radix = digits.length
    if i < radix:
        return digits[i]
    return itoa(i // radix) + digits[i % radix]
