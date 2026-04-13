<!--
A new scriv changelog fragment.

Uncomment the section that is right (remove the HTML comment wrapper).
For top level release notes, leave all the headers commented out.
-->

<!--
### Removed

- A bullet item for the Removed category.

-->
<!--
### Added

- A bullet item for the Added category.

-->
<!--
### Changed

- A bullet item for the Changed category.

-->
<!--
### Deprecated

- A bullet item for the Deprecated category.

-->
### Fixed

- Fixed a miscompilation where biguint `x ^ x` was folded to an empty-bytes constant, losing the input byte-width. The AVM `b^` op produces a zero-filled array of the same length as its inputs.
<!--
### Security

- A bullet item for the Security category.

-->
