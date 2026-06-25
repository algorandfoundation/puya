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

- A bug when OCA is one of (UpdateApplication, CloseOut) and creation is required or allowed in an abi or bare method, silently leaving those options out of arc56 clients. We now emit warning/s and/or error when this happens, according to the severity of the OCA+create combination (e.g. 'CloseOut' only on a creation required method will always fail potentially compiling an undeployable contract)


<!--
### Security

- A bullet item for the Security category.

-->
