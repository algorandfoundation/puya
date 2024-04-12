def test_hello_world():
    from algopy import String

    from examples.hello_world_arc4.contract import HelloWorldContract

    client = HelloWorldContract()
    result = client.hello(String("World!"))
    assert result == "Hello, World!"
