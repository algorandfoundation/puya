// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class Hello extends Contract {

    @abimethod({ onCreate: 'require' })
    create(
        greeting: arc4.Str,
    ): void {
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
    ): arc4.Str {
        err("stub only")
    }
}
