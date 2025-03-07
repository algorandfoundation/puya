from algopy import ARC4Contract, String, arc4, ImmutableArray


# Note: this contract is also used in the Puya AlgoKit template. So any breaking changes
# that require fixing this contract should also be made there
# https://github.com/algorandfoundation/algokit-puya-template/blob/main/template_content/pyproject.toml.jinja
# https://github.com/algorandfoundation/algokit-puya-template/blob/main/template_content/.algokit/generators/create_contract/smart_contracts/%7B%25%20raw%20%25%7D%7B%7B%20contract_name%20%7D%7D%7B%25%20endraw%20%25%7D/contract.py.j2


class HelloWorldContract(ARC4Contract):
    @arc4.abimethod
    def hello(self, name: String) -> String:
        arr = ImmutableArray[arc4.Address]()
        arr = arr.append(arc4.Address())
        arr = arr.append(arc4.Address())
        arc4.abi_call(
            Foo.verify,
            arr,
            app_id=1234
        )
        return "Hello, " + name


class Foo(ARC4Contract):

    @arc4.abimethod
    def verify(self, arr: ImmutableArray[arc4.Address]) -> None:
        pass
