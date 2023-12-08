import typing

from algopy import (
    ARC4Contract,
    Box,
    Bytes,
    CreateInnerTransaction,
    Global,
    InnerTransaction,
    OpUpFeeSource,
    PaymentTransaction,
    Transaction,
    TransactionType,
    UInt64,
    arc4,
    btoi,
    ensure_budget,
    extract,
    itob,
    log,
    subroutine,
    urange,
    ed25519verify_bare,
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
        self.close_time = UInt64(0)
        self.nft_asset_id = UInt64(0)

        self.snapshot_public_key = Bytes()
        self.vote_id = Bytes()
        self.metadata_ipfs_cid = Bytes()
        self.start_time = UInt64(0)
        self.end_time = UInt64(0)
        self.quorum = UInt64(0)
        self.nft_image_url = Bytes()
        self.option_counts = VoteIndexArray()
        self.total_options = UInt64(0)

    def clear_state_program(self) -> bool:
        return True

    @arc4.abimethod(create=True)
    def create(
        self,
        vote_id: arc4.String,
        snapshot_public_key: arc4.DynamicBytes,
        metadata_ipfs_cid: arc4.String,
        start_time: arc4.UInt64,
        end_time: arc4.UInt64,
        option_counts: VoteIndexArray,
        quorum: arc4.UInt64,
        nft_image_url: arc4.String,
    ) -> None:
        st = start_time.decode()
        et = end_time.decode()
        assert st < et, "End time should be after start time"
        assert et >= Global.latest_timestamp(), "End time should be in the future"

        self.vote_id = vote_id.decode()
        self.snapshot_public_key = snapshot_public_key.bytes[2:]
        self.metadata_ipfs_cid = metadata_ipfs_cid.decode()
        self.start_time = st
        self.end_time = et
        self.quorum = quorum.decode()
        self.nft_image_url = nft_image_url.decode()
        self.store_option_counts(option_counts)

    @arc4.abimethod()
    def bootstrap(self, fund_min_bal_req: PaymentTransaction) -> None:
        assert not self.is_bootstrapped, "Must not be already bootstrapped"
        self.is_bootstrapped = True

        bytes_per_option = UInt64(8)
        box_cost = (
            BOX_FLAT_MIN_BALANCE
            + BOX_BYTE_MIN_BALANCE
            + (self.total_options * BOX_BYTE_MIN_BALANCE * bytes_per_option)
        )

        min_balance_req = ASSET_MIN_BALANCE * 2 + 1000 + box_cost
        assert (
            fund_min_bal_req.receiver == Global.current_application_address()
        ), "Payment must be to app address"
        log(itob(min_balance_req))

        assert (
            fund_min_bal_req.amount == min_balance_req
        ), "Payment must be for the exact min balance requirement"

        assert Box.create(TALLY_BOX_KEY, self.total_options * VOTE_COUNT_BYTES)

    @arc4.abimethod()
    def close(self) -> None:
        ensure_budget(20000, fee_source=OpUpFeeSource.GroupCredit)
        assert self.close_time == 0, "Already closed"
        self.close_time = Global.latest_timestamp()

        note = (
            b'{"standard":"arc69",'
            b'"description":"This is a voting result NFT for voting round with ID '
            + self.vote_id
            + b'.","properties":{"metadata":"ipfs://'
            + self.metadata_ipfs_cid
            + b'","id":"'
            + self.vote_id
            + b'","quorum":'
            + itob(self.quorum)
            + b',"voterCount":'
            + itob(self.voter_count)
            + b',"tallies":['
        )

        current_index = UInt64(0)
        for question_index in urange(self.option_counts.length):
            question_options = self.option_counts[question_index].decode()
            for option_index in urange(question_options):
                votes_for_option = get_vote_from_box(current_index)
                note += (
                    Bytes(b"[")
                    if option_index == 0
                    else Bytes(b"") + itob(votes_for_option) + Bytes(b"]")
                    if option_index == (question_options - 1)
                    else Bytes(b",")
                    if question_index == (self.option_counts.length - 1)
                    else Bytes(b"")
                )
                current_index += 1
        note += b"]}}"
        CreateInnerTransaction.begin()
        CreateInnerTransaction.set_type_enum(TransactionType.AssetConfig)
        CreateInnerTransaction.set_config_asset_total(1)
        CreateInnerTransaction.set_config_asset_decimals(0)
        CreateInnerTransaction.set_config_asset_default_frozen(False)
        CreateInnerTransaction.set_config_asset_name(b"[VOTE RESULT] " + self.vote_id)
        CreateInnerTransaction.set_config_asset_unit_name(b"VOTERSLT")
        CreateInnerTransaction.set_config_asset_url(self.nft_image_url)
        CreateInnerTransaction.set_note(note)
        CreateInnerTransaction.submit()
        self.nft_asset_id = InnerTransaction.created_asset_id()

    @arc4.abimethod(readonly=True)
    def get_preconditions(self, signature: arc4.DynamicBytes) -> VotingPreconditions:
        return VotingPreconditions(
            is_voting_open=arc4.UInt64(self.voting_open()),
            is_allowed_to_vote=arc4.UInt64(self.allowed_to_vote(signature.bytes[2:])),
            has_already_voted=arc4.UInt64(self.already_voted()),
            current_time=arc4.UInt64(Global.latest_timestamp()),
        )

    @arc4.abimethod()
    def vote(
        self,
        fund_min_bal_req: PaymentTransaction,
        signature: arc4.DynamicBytes,
        answer_ids: VoteIndexArray,
    ) -> None:
        # return pt.Seq(
        ensure_budget(7700, fee_source=OpUpFeeSource.GroupCredit)
        # Check voting preconditions
        assert self.allowed_to_vote(signature.bytes[2:]), "Not allowed to vote"
        assert self.voting_open(), "Voting not open"
        assert not self.already_voted(), "Already voted"
        questions_count = self.option_counts.length
        assert answer_ids.length == questions_count, "Number of answers incorrect"
        # Check voter box is funded
        min_bal_req = BOX_FLAT_MIN_BALANCE + (
            (32 + 2 + VOTE_INDEX_BYTES * answer_ids.length) * BOX_BYTE_MIN_BALANCE
        )
        assert (
            fund_min_bal_req.receiver == Global.current_application_address()
        ), "Payment must be to app address"

        log(itob(min_bal_req))
        assert fund_min_bal_req.amount == min_bal_req, "Payment must be the exact min balance"
        # Record the vote for each question
        cumulative_offset = UInt64(0)
        for question_index in urange(questions_count):
            # Load the user's vote for this question
            answer_option_index = answer_ids[question_index]
            options_count = self.option_counts[question_index]
            assert (
                answer_option_index.decode() < options_count.decode()
            ), "Answer option index invalid"
            increment_vote_in_box(cumulative_offset + answer_option_index.decode())
            cumulative_offset += options_count.decode()
            Box.put(Transaction.sender().bytes, answer_ids.bytes)
            self.voter_count += 1

    @subroutine
    def voting_open(self) -> bool:
        return (
            self.is_bootstrapped
            and not self.close_time
            and self.start_time <= Global.latest_timestamp() <= self.end_time
        )

    @subroutine
    def already_voted(self) -> bool:
        (votes, exists) = Box.get(Transaction.sender().bytes)
        return exists

    @subroutine
    def store_option_counts(self, option_counts: VoteIndexArray) -> None:
        assert option_counts.length, "option_counts should be non-empty"

        assert option_counts.length <= 112, "Can't have more than 112 questions"

        self.option_counts = option_counts

        total_options = self.calculate_total_options_count(option_counts)
        assert total_options <= 128, "Can't have more than 128 vote options"
        self.total_options = total_options

    @subroutine
    def calculate_total_options_count(self, option_counts: VoteIndexArray) -> UInt64:
        total = UInt64(0)
        for item in option_counts:
            total += item.decode()

        return total

    @subroutine
    def allowed_to_vote(self, signature: Bytes) -> bool:
        ensure_budget(2000)
        return ed25519verify_bare(
            Transaction.sender().bytes,
            signature,
            self.snapshot_public_key,
        )


@subroutine
def get_vote_from_box(index: UInt64) -> UInt64:
    box_data, exists = Box.get(TALLY_BOX_KEY)
    assert exists, "Box not created"
    return btoi(extract(box_data, index, VOTE_COUNT_BYTES))


@subroutine
def increment_vote_in_box(index: UInt64) -> None:
    box_data, exists = Box.get(TALLY_BOX_KEY)
    assert exists, "Box not created"
    current_vote = btoi(extract(box_data, index, VOTE_COUNT_BYTES))
    Box.replace(TALLY_BOX_KEY, index, itob(current_vote + 1))
