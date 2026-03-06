import typing

from algopy import Account, Bytes, String, UInt64

_TKey = typing.TypeVar("_TKey")
_TValue = typing.TypeVar("_TValue")
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

@typing.final
class GlobalMap(typing.Generic[_TKey, _TValue]):
    """
    GlobalMap abstracts the reading and writing of a set of global state values using a
    common key and content type.
    Adequate space must be allocated for the application on creation (see algopy.StateTotals).
    """

    def __init__(
        self,
        key_type: type[_TKey],
        value_type: type[_TValue],
        /,
        *,
        key_prefix: bytes | str | Bytes | String = ...,
    ) -> None:
        """Declare a global map.

        :arg key_type: The type of the keys
        :arg value_type: The type of the values
        :arg key_prefix: The value used as a prefix to key data, can be empty.
                         When the GlobalMap is being assigned to a member variable,
                         this argument is optional and defaults to the member variable name,
                         and if a custom value is supplied it must be static.
        """

    @property
    def key_prefix(self) -> Bytes:
        """Provides access to the raw storage key-prefix."""

    def __getitem__(self, key: _TKey) -> _TValue:
        """Retrieve the value associated with key. Fails if the key has not been defined.

        ```python
        value = self.map[key]
        ```
        """

    def __setitem__(self, key: _TKey, value: _TValue) -> None:
        """Write value to global state.

        ```python
        self.map[key] = value
        ```
        """

    def __delitem__(self, key: _TKey) -> None:
        """Deletes a global state value.

        ```python
        del self.map[key]
        ```
        """

    def __contains__(self, key: _TKey) -> bool:
        """
        Returns True if a specified key exists in the map, regardless of the
        truthiness of the contents of the value.

        ```python
        assert key in self.map
        ```
        """

    def get(self, key: _TKey, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents, or return the default value if the key is not present.

        :arg key: The key to get
        :arg default: The default value to return if the key is not present.
        """

    def maybe(self, key: _TKey) -> tuple[_TValue, bool]:
        """
        Retrieve the contents if it exists, and return a boolean indicating if the
        key was present.

        :arg key: The key to get
        """

    def state(self, key: _TKey) -> GlobalState[_TValue]:
        """
        Returns a GlobalState for the value at key.
        """

@typing.final
class LocalMap(typing.Generic[_TKey, _TValue]):
    """
    LocalMap abstracts the reading and writing of a set of local state values using a
    common key and content type, associated with a specific account.
    Adequate space must be allocated for the application on creation (see algopy.StateTotals).
    """

    def __init__(
        self,
        key_type: type[_TKey],
        value_type: type[_TValue],
        /,
        *,
        key_prefix: bytes | str | Bytes | String = ...,
    ) -> None:
        """Declare a local map.

        :arg key_type: The type of the keys
        :arg value_type: The type of the values
        :arg key_prefix: The value used as a prefix to key data, can be empty.
                         When the LocalMap is being assigned to a member variable,
                         this argument is optional and defaults to the member variable name,
                         and if a custom value is supplied it must be static.
        """

    @property
    def key_prefix(self) -> Bytes:
        """Provides access to the raw storage key-prefix."""

    def __getitem__(self, account_and_key: tuple[Account | UInt64 | int, _TKey]) -> _TValue:
        """
        Retrieve the value associated with account and key.
        Fails if the key has not been defined.

        ```python
        value = self.map[account, key]
        ```
        """

    def __setitem__(
        self, account_and_key: tuple[Account | UInt64 | int, _TKey], value: _TValue
    ) -> None:
        """Write value to local state for the given account and key.

        ```python
        self.map[account, key] = value
        ```
        """

    def __delitem__(self, account_and_key: tuple[Account | UInt64 | int, _TKey]) -> None:
        """Deletes a local state value for the given account and key.

        ```python
        del self.map[account, key]
        ```
        """

    def __contains__(self, account_and_key: tuple[Account | UInt64 | int, _TKey]) -> bool:
        """
        Returns True if a specified key exists in the map for the given account,
        regardless of the truthiness of the contents of the value.

        ```python
        assert (account, key) in self.map
        ```
        """

    def get(self, account: Account | UInt64 | int, key: _TKey, *, default: _TValue) -> _TValue:
        """
        Retrieve the contents, or return the default value if the key is not present
        for the given account.

        :arg account: The account reference or foreign account index
        :arg key: The key to get
        :arg default: The default value to return if the key is not present.
        """

    def maybe(self, account: Account | UInt64 | int, key: _TKey) -> tuple[_TValue, bool]:
        """
        Retrieve the contents if it exists for the given account, and return a boolean
        indicating if the key was present.

        :arg account: The account reference or foreign account index
        :arg key: The key to get
        """

    def state(self, key: _TKey) -> LocalState[_TValue]:
        """
        Returns a LocalState for the value at key.
        The returned LocalState still requires an account to access its value.

        ```python
        state = self.map.state(key)
        value = state[account]
        ```
        """
