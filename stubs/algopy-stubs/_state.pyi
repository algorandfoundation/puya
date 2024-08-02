import typing

from algopy import Account, Bytes, String, UInt64

_TState = typing.TypeVar("_TState")

@typing.final
class LocalState(typing.Generic[_TState]):
    """Local state associated with the application and an account"""

    def __init__(
        self: LocalState[_TState],
        type_: type[_TState],
        /,
        *,
        key: String | Bytes | bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the local state key and it's associated type

        ```python
        self.names = LocalState(algopy.Bytes)
        ```
        """

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    def __getitem__(self, account: Account | UInt64 | int) -> _TState:
        """Data can be accessed by an `Account` reference or foreign account index

        ```python
        account_name = self.names[account]
        ```
        """

    def __setitem__(self, account: Account | UInt64 | int, value: _TState) -> None:
        """Data can be stored by using an `Account` reference or foreign account index

        ```python
        self.names[account] = account_name
        ```
        """

    def __delitem__(self, account: Account | UInt64 | int) -> None:
        """Data can be removed by using an `Account` reference or foreign account index

        ```python
        del self.names[account]
        ```
        """

    def __contains__(self, account: Account | UInt64 | int) -> bool:
        """Can test if data exists by using an `Account` reference or foreign account index

        ```python
        assert account in self.names
        ```
        """

    def get(self, account: Account | UInt64 | int, default: _TState) -> _TState:
        """Can retrieve value using an `Account` reference or foreign account index,
        and a fallback default value.

        ```python
        name = self.names.get(account, Bytes(b"no name")
        ```
        """

    def maybe(self, account: Account | UInt64 | int) -> tuple[_TState, bool]:
        """Can retrieve value, and a bool indicating if the value was present
        using an `Account` reference or foreign account index.

        ```python
        name, name_exists = self.names.maybe(account)
        if not name_exists:
            name = Bytes(b"no name")
        ```
        """

@typing.final
class GlobalState(typing.Generic[_TState]):
    """Global state associated with the application, the key will be the name of the member, this
    is assigned to

    ```{note}
    The `GlobalState` class provides a richer API that in addition to storing and retrieving
    values, can test if a value is set or unset it. However if this extra functionality is not
    needed then it is simpler to just store the data without the GlobalState proxy
    e.g. `self.some_variable = UInt64(0)`
    ```
    """

    @typing.overload
    def __init__(
        self: GlobalState[_TState],
        type_: type[_TState],
        /,
        *,
        key: String | Bytes | bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the global state key and its type without initializing its value"""

    @typing.overload
    def __init__(
        self: GlobalState[_TState],
        initial_value: _TState,
        /,
        *,
        key: bytes | str = ...,
        description: str = "",
    ) -> None:
        """Declare the global state key and initialize its value"""

    @property
    def key(self) -> Bytes:
        """Provides access to the raw storage key"""

    @property
    def value(self) -> _TState:
        """Returns the value or and error if the value is not set

        ```python
        name = self.name.value
        ```
        """

    @value.setter
    def value(self, value: _TState) -> None:
        """Sets the value

        ```python
        self.name.value = Bytes(b"Alice")
        ```
        """

    @value.deleter
    def value(self) -> None:
        """Removes the value

        ```python
        del self.name.value
        ```
        """

    def __bool__(self) -> bool:
        """Returns `True` if the key has a value set, regardless of the truthiness of that value"""

    def get(self, default: _TState) -> _TState:
        """Returns the value or `default` if no value is set

        ```python
        name = self.name.get(Bytes(b"no name")
        ```
        """

    def maybe(self) -> tuple[_TState, bool]:
        """Returns the value, and a bool

        ```python
        name, name_exists = self.name.maybe()
        if not name_exists:
            name = Bytes(b"no name")
        ```
        """
