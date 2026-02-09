// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class HelloOtherConstants extends Contract {

    @abimethod({ onCreate: 'require' })
    create(

    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod({ allowActions: ['DeleteApplication'] })
    delete(

    ): void {
        err("stub only")
    }

    @abimethod
    greet(
        name: arc4.Str,
    ): arc4.DynamicBytes {
        err("stub only")
    }
}
