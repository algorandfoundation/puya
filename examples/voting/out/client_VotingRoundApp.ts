// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class VotingPreconditions extends arc4.Struct<{
    is_voting_open: arc4.Uint<64>,
    is_allowed_to_vote: arc4.Uint<64>,
    has_already_voted: arc4.Uint<64>,
    current_time: arc4.Uint<64>,
}> { }

export abstract class VotingRoundApp extends Contract {

    @abimethod({ onCreate: 'require' })
    create(
        vote_id: arc4.Str,
        snapshot_public_key: arc4.DynamicBytes,
        metadata_ipfs_cid: arc4.Str,
        start_time: arc4.Uint<64>,
        end_time: arc4.Uint<64>,
        option_counts: arc4.DynamicArray<arc4.Uint<8>>,
        quorum: arc4.Uint<64>,
        nft_image_url: arc4.Str,
    ): void {
        err("stub only")
    }

    @abimethod
    bootstrap(
        fund_min_bal_req: gtxn.PaymentTxn,
    ): void {
        err("stub only")
    }

    @abimethod
    close(

    ): void {
        err("stub only")
    }

    @abimethod({ readonly: True })
    get_preconditions(
        signature: arc4.DynamicBytes,
    ): VotingPreconditions {
        err("stub only")
    }

    @abimethod
    vote(
        fund_min_bal_req: gtxn.PaymentTxn,
        signature: arc4.DynamicBytes,
        answer_ids: arc4.DynamicArray<arc4.Uint<8>>,
    ): void {
        err("stub only")
    }
}
