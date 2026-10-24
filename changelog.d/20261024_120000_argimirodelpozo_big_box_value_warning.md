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

- Aligned compiler behaviour and documentation for box values larger than 4096 bytes. Loading such a value as a whole (e.g. passing it to a subroutine, returning it or copying it into a local variable) always fails at runtime, and now emits a compile warning when its reasonable to assume the size from a fixed-size declared type. Dynamically sized values do not emit a warning, but may still fail at runtime if they grow larger than 4096 bytes (see the size constraints documentation).

<!--
### Security

- A bullet item for the Security category.

-->
