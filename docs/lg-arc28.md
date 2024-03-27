# ARC-28: Structured event logging

[ARC-28](https://github.com/algorandfoundation/ARCs/blob/main/ARCs/arc-0028.md) provides a methodology for structured logging by Algorand smart contracts. It introduces the concept of Events, where data contained in logs may be categorized and structured.

Each Event is identified by a unique 4-byte identifier derived from its `Event Signature`. The Event Signature is a UTF-8 string comprised of the event's name, followed by the names of the [ARC-4](./lg-arc4.md) data types contained in the event, all enclosed in parentheses (`EventName(type1,type2,...)`) e.g.:

```
Swapped(uint64,uint64)
```

Events are emitting by including them in the [log output](./lg-logs.md). The metadata that identifies the event should then be included in the ARC-4 contract output so that a calling client can parse the logs to parse the structured data out. This part of the ARC-28 spec isn't yet implemented in Algorand Python, but it's on the roadmap.

## Emitting Events

To emit an ARC-28 event in Algorand Python you can use the `emit` function, which appears in the `algopy.arc4` namespace for convenience since it heavily uses ARC-4 types and is essentially an extension of the ARC-4 specification. This function takes care of encoding the event payload to conform to the ARC-28 specification and there are 3 overloads:

-   An [ARC-4 struct](./lg-arc4.md), from what the name of the struct will be used as a the event name and the struct parameters will be used as the event fields - `arc4.emit(Swapped(a, b))`
-   An event signature as a [string literal (or module variable)](./lg-types.md), followed by the values - `arc4.emit("Swapped(uint64,uint64)", a, b)`
-   An event name as a [string literal (or module variable)](./lg-types.md), followed by the values - `arc4.emit("Swapped", a, b)`

Here's an example contract that emits events:

```python
from algopy import ARC4Contract, arc4

class Swapped(arc4.Struct):
    a: arc4.UInt64
    b: arc4.UInt64

class EventEmitter(ARC4Contract):
    @arc4.abimethod
    def emit_swapped(self, a: arc4.UInt64, b: arc4.UInt64) -> None:
        arc4.emit(Swapped(b, a))
        arc4.emit("Swapped(uint64,uint64)", b, a)
        arc4.emit("Swapped", b, a)
```

It's worth noting that the ARC-28 event signature needs to be known at compile time so the event name can't be a dynamic type and must be a static string literal or string module constant. If you want to emit dynamic events you can do so using the [`log` method](./lg-logs.md), but you'd need to manually construct the correct series of bytes and the compiler won't be able to emit the ARC-28 metadata so you'll need to also manually parse the logs in your client.

Examples of manually constructing an event:

```python
# This is essentially what the `emit` method is doing, noting that a,b need to be encoded
#   as a tuple so below (simple concat) only works for static ARC-4 types
log(arc4.arc4_signature("Swapped(uint64,uint64)"), a, b)

# or, if you wanted it to be truly dynamic for some reason,
#   (noting this has a non-trivial opcode cost) and assuming in this case
#   that `event_suffix` is already defined as a `String`:
event_name = String("Event") + event_suffix
event_selector = op.sha512_256((event_name + "(uint64)").bytes)[:4]
log(event_selector, UInt64(6))
```
