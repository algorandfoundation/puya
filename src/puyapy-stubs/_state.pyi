import typing

from puyapy import Account, UInt64

_T = typing.TypeVar("_T")

class LocalState(typing.Generic[_T]):
    """Local state associated with the application and an account"""

    def __init__(self, type_: type[_T], /) -> None:
        """Must be initialized with the type that will be stored

        ```python
        self.names = LocalState(puyapy.Bytes)
        ```
        """
    def __getitem__(self, account: Account | UInt64 | int) -> _T:
        """Data can be accessed by an `Account` reference or foreign account index

        ```python
        account_name = self.names[account]
        ```
        """
    def __setitem__(self, account: Account | UInt64 | int, value: _T) -> None:
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
    def get(self, account: Account | UInt64 | int, default: _T) -> _T:
        """Can retrieve value using an `Account` reference or foreign account index,
        and a fallback default value.

        ```python
        name = self.names.get(account, Bytes(b"no name")
        ```
        """
    def maybe(self, account: Account | UInt64 | int) -> tuple[_T, bool]:
        """Can retrieve value, and a bool indicating if the value was present
        using an `Account` reference or foreign account index.

        ```python
        name, name_exists = self.names.maybe(account)
        if not name_exists:
            name = Bytes(b"no name")
        ```
        """

class GlobalState(typing.Generic[_T]):
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
    def __init__(self, type_: type[_T], /) -> None:
        """Can be initialized with the type of the value to store, with the value unset"""
    @typing.overload
    def __init__(self, initial_value: _T, /) -> None:
        """Can be initialized with an initial value"""
    @property
    def value(self) -> _T:
        """Returns the value or and error if the value is not set

        ```python
        name = self.name.value
        ```
        """
    @value.setter
    def value(self, value: _T) -> None:
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
    def get(self, default: _T) -> _T:
        """Returns the value or `default` if no value is set

        ```python
        name = self.name.get(Bytes(b"no name")
        ```
        """
    def maybe(self) -> tuple[_T, bool]:
        """Returns the value, and a bool

        ```python
        name, name_exists = self.name.maybe()
        if not name_exists:
            name = Bytes(b"no name")
        ```
        """
