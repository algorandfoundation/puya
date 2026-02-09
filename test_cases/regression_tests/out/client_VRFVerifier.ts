// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'


export abstract class VRFVerifier extends Contract {

    @abimethod
    verify(
        message: arc4.DynamicBytes,
        proof: arc4.DynamicBytes,
        pk: arc4.DynamicBytes,
    ): arc4.Tuple<readonly [arc4.DynamicBytes, arc4.Bool]> {
        err("stub only")
    }
}
