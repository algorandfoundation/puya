"""Example 11: Contract Factory

This example demonstrates compile_contract, arc4.arc4_create, and contract-to-contract calls.

Features:
- compile_contract() — compile a child contract class, get CompiledContract properties
- arc4.arc4_create() — typed compilation + deployment returning created app
- arc4.abi_call() — contract-to-contract ABI method invocation with return values
- arc4.arc4_signature() — get 4-byte ARC4 method selector
- TemplateVar — compile-time template variable substitution in child contract
- CompiledContract properties (approval_program, clear_state_program, global_uints, etc.)
- Contract-to-contract calls via inner transactions

Prerequisites: LocalNet

Note: Educational only — not audited for production use.
"""

from algopy import (
    ARC4Contract,
    Application,
    String,
    TemplateVar,
    UInt64,
    arc4,
    compile_contract,
    itxn,
)


class ChildContract(ARC4Contract):
    """A child contract that receives its greeting at create time."""

    def __init__(self) -> None:
        self.greeting = String()

    @arc4.abimethod(create="require")
    def create(self, greeting: String) -> None:
        """Create handler — accepts a greeting string to store in global state.

        Args:
            greeting: the greeting prefix to store
        """
        self.greeting = greeting

    @arc4.abimethod()
    def greet(self, name: String) -> String:
        """Return a personalized greeting combining stored state with the given name.

        Args:
            name: the name to greet

        Returns:
            the personalized greeting string
        """
        return self.greeting + " " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        """Allow deletion of this app (used by factory cleanup)."""


class TemplatedChild(ARC4Contract):
    """A child contract whose greeting is fixed at compile time via TemplateVar."""

    def __init__(self) -> None:
        # TemplateVar — value injected at compile time via compile_contract() template_vars option
        self.greeting = TemplateVar[String]("GREETING")

    @arc4.abimethod(create="require")
    def create(self) -> None:
        """Create handler — greeting is set by TemplateVar in __init__."""

    @arc4.abimethod()
    def greet(self, name: String) -> String:
        """Return a personalized greeting combining stored state with the given name.

        Args:
            name: the name to greet

        Returns:
            the personalized greeting string
        """
        return self.greeting + " " + name

    @arc4.abimethod(allow_actions=["DeleteApplication"])
    def delete(self) -> None:
        """Allow deletion of this app (used by factory cleanup)."""


# ═══════════════════════════════════════════════════════════════════
# Factory Contract — deploys and manages child contract instances
# ═══════════════════════════════════════════════════════════════════


class ContractFactory(ARC4Contract):
    """Factory that compiles and deploys child contracts on-chain.

    Demonstrates compile_contract(), TemplateVar substitution,
    and contract-to-contract (C2C) calls via inner transactions.
    """

    @arc4.abimethod()
    def deploy_child(self, greeting: String) -> UInt64:
        """Deploy a child using compile_contract() — manual inner transaction approach.

        Demonstrates compile_contract(), CompiledContract properties,
        arc4_signature(), and ARC4 encoding.

        Args:
            greeting: the greeting prefix to pass to the child

        Returns:
            the deployed child Application ID
        """
        # compile_contract() — compiles ChildContract
        compiled = compile_contract(ChildContract)

        # CompiledContract properties — access compiled program bytecode and state schema
        # arc4_signature() — get 4-byte ARC4 method selector
        child_app = (
            itxn.ApplicationCall(
                app_args=(arc4.arc4_signature("create(string)void"), arc4.String(greeting)),
                approval_program=compiled.approval_program,
                clear_state_program=compiled.clear_state_program,
                global_num_uint=compiled.global_uints,
                global_num_bytes=compiled.global_bytes,
                local_num_uint=compiled.local_uints,
                local_num_bytes=compiled.local_bytes,
            )
            .submit()
            .created_app
        )
        return child_app.id

    @arc4.abimethod()
    def deploy_templated(self) -> UInt64:
        """Deploy a child using compile_contract() with TemplateVar — typed create approach.

        Demonstrates compile_contract() with template_vars and arc4_create().

        Returns:
            the deployed child Application ID
        """
        # compile_contract() with template_vars — compile-time variable substitution
        compiled = compile_contract(
            TemplatedChild,
            template_vars={"GREETING": String("howdy")},
        )

        # arc4_create() — typed deployment dispatching a correctly-formed inner txn
        child_app = arc4.arc4_create(TemplatedChild.create, compiled=compiled).created_app
        return child_app.id

    @arc4.abimethod()
    def call_child_greet(self, app: Application, name: String) -> String:
        """Call a deployed child's greet() method using abi_call().

        Demonstrates abi_call() with method reference, args, and return value extraction.

        Args:
            app: the child Application to call
            name: the name to pass to greet()

        Returns:
            the greeting string from the child
        """
        # abi_call() — invoke an ABI method on another contract, returns typed result
        result, _txn = arc4.abi_call(ChildContract.greet, name, app_id=app)
        return result

    @arc4.abimethod()
    def delete_child(self, app: Application) -> None:
        """Delete a deployed child contract using abi_call() with DeleteApplication.

        Args:
            app: the child Application to delete
        """
        # abi_call() with on_completion — invoke delete with DeleteApplication action
        arc4.abi_call(ChildContract.delete, app_id=app)

    @arc4.abimethod()
    def deploy_and_greet(self, greeting: String, name: String) -> String:
        """All-in-one: deploy child with arc4_create, greet via abi_call, then delete.

        Args:
            greeting: the greeting prefix for the new child
            name: the name to pass to greet()

        Returns:
            the greeting string from the child
        """
        child_app = arc4.arc4_create(ChildContract.create, greeting).created_app
        result, _txn = arc4.abi_call(ChildContract.greet, name, app_id=child_app)
        arc4.abi_call(ChildContract.delete, app_id=child_app)
        return result
