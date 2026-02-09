// This file is auto-generated, do not modify
import * from '@algorandfoundation/algorand-typescript'

export class StructOne extends arc4.Struct<{
    x: arc4.Uint<8>,
    y: arc4.Uint<8>,
}> { }

export class StructTwo extends arc4.Struct<{
    x: arc4.Uint<8>,
    y: arc4.Uint<8>,
}> { }

export class test_cases_struct_by_name_mod_StructTwo extends arc4.Struct<{
    x: arc4.Uint<8>,
    y: arc4.Uint<8>,
}> { }

/**
 * 
 *     Verify that even though named tuples with different names but the same structure should be
 *     considered 'comparable' in the type system, they should be output separately when being
 *     interpreted as an arc4 Struct in an abi method
 *     
 */
export abstract class DemoContract extends Contract {

    @abimethod
    get_one(

    ): StructOne {
        err("stub only")
    }

    @abimethod
    get_two(

    ): StructTwo {
        err("stub only")
    }

    @abimethod
    get_three(

    ): test_cases_struct_by_name_mod_StructTwo {
        err("stub only")
    }

    @abimethod
    compare(

    ): arc4.Bool {
        err("stub only")
    }
}
