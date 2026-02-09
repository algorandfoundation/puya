// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class UserStruct extends arc4.Struct<{
    name: arc4.Str,
    id: arc4.Uint<64>,
    asset: arc4.Uint<64>,
}> { }

export abstract class ExampleContract extends Contract {

    @abimethod
    add_user(
        user: UserStruct,
    ): void {
        err("stub only")
    }

    @abimethod
    attach_asset_to_user(
        user_id: arc4.Uint<64>,
        asset: arc4.Uint<64>,
    ): void {
        err("stub only")
    }

    @abimethod
    get_user(
        user_id: arc4.Uint<64>,
    ): UserStruct {
        err("stub only")
    }
}
