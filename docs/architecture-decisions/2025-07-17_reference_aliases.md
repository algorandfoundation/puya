# Steer users away from using reference aliases

JIRA: https://algorandfoundation.atlassian.net/browse/AK-72

## Problem 1: How to represent different behaviour

Currently the types `Asset`, `Application` and `Account` (also known as reference types due to corresponding aliases in the ARC-4 specification)
are always used in ABI methods as their appropriate reference alias (`asset`, `application`, `account`).

Instead it is desirable for these types to be represented in ABI methods as their underlying value types 
(`uint64` for Asset and Application, `address` for Account)

This is because it allows more efficient usage of foreign arrays (a limited resource) across a transaction group, and additionally
the new populate resources functionality in `algokit_utils` removes most of the friction around populating the foreign arrays that 
previously required reference aliases.

## Solutions

### 1: Distinct Types

This solution proposes having two types for each resource, e.g. `AssetId` and `AssetReference`, each type would represent the same resource
but would change how they are used in ABI methods e.g. `AssetId` would be seen as a `uint64`, while `AssetReference` would continue with
the existing behaviour of using `asset`

#### Pros

* Behaviour difference is represented at the type level
* Allows mixing both aliases and value ABI types in the same method (open question whether this is desirable or not)
* Same approach used by TEALScript

#### Cons

* Multiple types representing the same thing can cause confusion on which one to use
* Interaction between the two types hierarchies becomes complex, e.g. 
  * how should equality between types representing the same resource be handled
  * how should types referencing other resources be handled i.e. an Asset's owner is an Account
* The removal of existing types and introducing new types is a significant breaking change that would impact most contracts
* Would allow inconsistent combination of types e.g. using both an `AssetId` and `AssetReference`

#### Example 

```python
from algopy import *

class Contract(ARC4Contract):
    
    @arc4.abimethod()
    def asset_arg_with_alias(self, asset: AssetReference) -> None:
        # asset_arg_with_alias(asset)void
        pass

    @arc4.abimethod()
    def asset_arg_with_id(self, asset: AssetId) -> None:
        # asset_arg_with_id(uint64)void
        pass

```

### 2: ABI routing configuration

This solution proposes making routing behaviour a configurable option on the `abimethod` decorator and as a compiler option.
There would be no changes required to the existing type definitions `Asset`, `Application` and `Account`. 
Instead the configuration option would control how these types are handled in the ABI router and application specifications (ARC-32 and ARC-56) 

#### Pros

* Can be implemented as a breaking change or non-breaking change, depending on default behaviour chosen
* Ensure behaviour is consistent within a method/compilation unit
* Does not require any type changes

#### Cons

* Mixing reference usage within a method would require workarounds
* Behaviour change may not be immediately obvious to users as there would not be a compiler error, but there would be a change in output

#### Example

```python
from algopy import *

class Contract(ARC4Contract):
    
    @arc4.abimethod(use_reference_alias=True)
    def asset_arg_with_alias(self, asset: Asset) -> None:
        # asset_arg_with_alias(asset)void
        pass

    @arc4.abimethod(use_reference_alias=False) # this parameter is optional (see next method)
    def asset_arg_with_id1(self, asset: Asset) -> None:
        # asset_arg_with_id1(uint64)void
        pass

    @arc4.abimethod()
    def asset_arg_with_id2(self, asset: Asset) -> None:
        # asset_arg_with_id2(uint64)void
        pass

```

## Problem 2: How to communicate behaviour change

## Solutions

### 1: No change in default behaviour, but add the capability for desired behaviour

#### Pros
* Does not force a change on the user
* Low friction
* Allows a period to communicate and try the change before making it the default

#### Cons
* Reduces uptake of new behaviour
    

### 2: Change behaviour without requiring code or configuration change

#### Pros
* User does not need to do anything after updating
* Low friction
* Increases uptake of new behaviour

#### Cons
* Is a breaking change in compiler behaviour
* May not be immediately clear there is a change if they aren't using approvals or reading release notes


### 3: Change behaviour with a warning until the user explicitly chooses something

#### Pros
* User does not need to do anything after updating
* Low friction
* Increases uptake of new behaviour

#### Cons
* Is a breaking change in compiler behaviour
* Warning may cause confusion

### 4: Force a change in behaviour with an error, user must pick a path forward

#### Pros
* Forces user to make a decision

#### Cons
* High friction
* Is a breaking change in compiler behaviour
* Users who are unsure may opt for the old behaviour out of caution

## Chosen solutions

## Problem 1: How to represent different behaviour

**Chosen solution:** 2: ABI routing configuration

Making the behaviour controlled by configuration makes it easy to automatically migrate to the new behaviour, and easy for those
who want the old behaviour to opt into it. Additionally, it keeps the cognitive load low by not introducing new types

## Problem 2: How to communicate behaviour change

**Chosen solution:** 2: Change behaviour without requiring code or configuration change

For a large number of users the new behaviour should not be a huge problem, and it is easy to revert to the original behaviour if
desired. Changelogs and a migration guide will outline the changes and what to do to revert to the original behaviour if desired
