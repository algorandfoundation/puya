### Fixed

- A bug where appending to, extending or popping from a dynamic array of `bool` (or `arc4.Bool`) stored in a box (either directly or as a member of a struct) treated each element as a whole byte, while reads of the same array are bit packed. Reading a whole `bool` array that is a member of a struct in a box also extracted one byte per element rather than the bit packed size.
- Reads and writes of a `bool` element of a dynamic array in a box are now bounds checked against the array length. Previously an index beyond the end of the array, but within the last byte of the array, would silently read or write a padding bit.
