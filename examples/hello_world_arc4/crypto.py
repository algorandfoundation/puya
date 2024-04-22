from algopy import ARC4Contract, String, Bytes, arc4, op,

# Note: this contract is also used in the Puya AlgoKit template. So any breaking changes
# that require fixing this contract should also be made there
# https://github.com/algorandfoundation/algokit-puya-template/blob/main/template_content/pyproject.toml.jinja
# https://github.com/algorandfoundation/algokit-puya-template/blob/main/template_content/.algokit/generators/create_contract/smart_contracts/%7B%25%20raw%20%25%7D%7B%7B%20contract_name%20%7D%7D%7B%25%20endraw%20%25%7D/contract.py.j2


class HelloWorldContract(ARC4Contract):
    @arc4.abimethod
    def verify(self, message: String, signature: Bytes, public_key: Bytes) -> bool:
        return op.ed25519verify_bare(message.bytes, signature, public_key)

