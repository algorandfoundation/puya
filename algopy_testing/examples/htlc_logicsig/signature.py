import algopy
from algopy import logicsig


@logicsig
def hashed_time_locked_lsig() -> bool:
    # Participants
    seller = algopy.Account("6ZHGHH5Z5CTPCF5WCESXMGRSVK7QJETR63M3NY5FJCUYDHO57VTCMJOBGY")
    buyer = algopy.Account("7Z5PWO2C6LFNQFGHWKSK5H47IQP5OJW2M3HA2QPXTY3WTNP5NU2MHBW27M")

    # Contract parameters
    fee_limit = algopy.UInt64(1000)
    secret_hash = algopy.Bytes(
        b"+\xb8\rS{\x1d\xa3\xe3\x8b\xd3\x03a\xaa\x85V\x86\xbd\xe0\xea\xcdqb\xfe\xf6\xa2_\xe9{\xf5'\xa2["
    )
    timeout = algopy.UInt64(3000)

    # Transaction conditions
    is_payment = algopy.Txn.type_enum == algopy.TransactionType.Payment
    is_fee_acceptable = algopy.Txn.fee < fee_limit
    is_no_close_to = algopy.Txn.close_remainder_to == algopy.Global.zero_address
    is_no_rekey = algopy.Txn.rekey_to == algopy.Global.zero_address

    # Safety conditions
    safety_conditions = is_payment and is_no_close_to and is_no_rekey

    # Seller receives payment if correct secret is provided
    is_to_seller = algopy.Txn.receiver == seller
    is_secret_correct = algopy.op.sha256(algopy.op.arg(0)) == secret_hash
    seller_receives = is_to_seller and is_secret_correct

    # Buyer receives refund after timeout
    is_to_buyer = algopy.Txn.receiver == buyer
    is_after_timeout = algopy.Txn.first_valid > timeout
    buyer_receives_refund = is_to_buyer and is_after_timeout

    # Final contract logic
    return is_fee_acceptable and safety_conditions and (seller_receives or buyer_receives_refund)
