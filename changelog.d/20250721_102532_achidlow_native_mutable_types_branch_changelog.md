<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
### Added

- Boxes containing fixed-size types larger than 4K can now be created/read/updated, provided 
  the size of the innermost element being read/written is not larger than 4K.
- Improved reads and writes to nested fixed-size data types by reducing number of bounds checks 
  where possible to do so safely.
- Added `algopy.zero_bytes()` function to easily initialise fixed-size bytes-backed types to 
  all zero bytes.
- The optimiser can now detect when a storage key (box/global/local) is guaranteed to exist and 
  can eliminate some redundant asserts.
- Repeated operations of concatenation, addition, multiplication, and uint64 bitwise operations 
  involving two or more constants can now be optimized.
- Improved detection and elimination of redundant ARC-4 encode/decode operations, particularly 
  those involving nested data structures, or where data structures have equivalent encoding but 
  not identical types.
- Improved ARC-4 encoding generation for tuples with dynamically-sized elements.

<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
### Fixed
- Fixed a potential semantic compatibility bug when instantiating a new `algopy.arc4.Struct` 
  using keyword arguments. The arguments were being evaluated in the order of the fields on the 
  Struct class, rather than from left to right when being passed.
- Fixed a compilation failure when using `--locals-coalescing-strategy=aggressive` option in 
  combination with `algopy.ReferenceArray`.
- Fixed a compilation failure when subroutines contained extremely long control flow sequences.
- Fixed a compilation failure when attempting to iterate an empty tuple.

<!--
### Security

- A bullet item for the Security category.

-->
