// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class MyContract extends Contract {

    @abimethod({ onCreate: 'require' })
    create(

    ): void {
        err("stub only")
    }

    @abimethod({ allowActions: ['NoOp', 'OptIn'] })
    register(
        name: arc4.Str,
    ): void {
        err("stub only")
    }

    @abimethod
    say_hello(

    ): arc4.Str {
        err("stub only")
    }

    @abimethod
    calculate(
        a: arc4.Uint<64>,
        b: arc4.Uint<64>,
    ): arc4.Uint<64> {
        err("stub only")
    }

    @abimethod({ allowActions: ['CloseOut'] })
    close_out(

    ): void {
        err("stub only")
    }
}
