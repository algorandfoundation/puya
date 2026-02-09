// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class MerkleTree extends Contract {

    @abimethod({ onCreate: 'require' })
    create(
        root: FixedArray<arc4.Byte, 32>,
    ): void {
        err("stub only")
    }

    @abimethod
    verify(
        proof: arc4.DynamicArray<FixedArray<arc4.Byte, 32>>,
        leaf: FixedArray<arc4.Byte, 32>,
    ): arc4.Bool {
        err("stub only")
    }
}
