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

- Fix an issue where a subroutine that never returns could be generated with ops that will 
  always fail at runtime (specifically, using `frame_dig` and/or `frame_bury` in a subroutine 
  that is detected as not requiring a `proto` instruction).

<!--
### Security

- A bullet item for the Security category.

-->
