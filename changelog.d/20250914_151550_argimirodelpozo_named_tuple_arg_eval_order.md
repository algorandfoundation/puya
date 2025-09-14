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

- Fixed [an issue](https://github.com/algorandfoundation/puya/issues/498) of semantic incompatibility concerning the order of evaluation of arguments when constructing named tuples.
Previously, arguments were evaluated in the order of field declarations in the named tuple type, rather than in the order they appear in the instantiating call. This could cause different results when arguments have side effects.


<!--
### Security

- A bullet item for the Security category.

-->
