// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class ATuple extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export class AStruct extends arc4.Struct<{
    a: arc4.Uint<64>,
    b: arc4.Uint<64>,
}> { }

export abstract class TemplateVariablesContract extends Contract {

    @abimethod
    get_bytes(

    ): arc4.DynamicBytes {
        err("stub only")
    }

    @abimethod
    get_big_uint(

    ): arc4.Uint<512> {
        err("stub only")
    }

    @abimethod
    get_a_named_tuple(

    ): ATuple {
        err("stub only")
    }

    @abimethod
    get_a_tuple(

    ): arc4.Tuple<readonly [arc4.Uint<64>, arc4.Uint<64>]> {
        err("stub only")
    }

    @abimethod
    get_a_struct(

    ): AStruct {
        err("stub only")
    }
}
