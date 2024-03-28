# Code reuse

## Imports

## Inheritance

TODO: expand upon

Contracts only
* Abstract methods
* super()
* BaseClass.method(self, ...)
* Multiple inheritance
* subroutine, abimethod, baremethod decorators

## Publishing reusable code

TODO: expand upon

Requirements for package to be imported successfully

* Include `py.typed` file 
* Include `__init__.py`
* Dependency on `algorand-python`
* Same requirements apply as other Algorand Python code 
* Projects created via `algokit init -t python` template are already capable of producing a wheel using poetry `poetry build` 
* Ensure passes `puyapy --no-output-teal --no-output-arc32`
