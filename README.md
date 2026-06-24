# decorules

## What is it?

_decorules_ is a small Python library (requires Python ≥ 3.10) with two goals:

**A. Enforce rules on class structure and instance behaviour** through decorators placed at class declaration time. Useful for library authors who want to guarantee that derived classes always respect certain contracts.

**B. Trigger user-defined functionality** based on boolean conditions on class instances — callbacks, logging, side-effects, etc.

## Installation

```
pip install decorules
```

## Quick Start

```python
import operator
from decorules import (
    HasRulesActions,
    raise_if_false_on_class,
    raise_if_false_on_instance,
    run_instance_rules,
    member_enforcer,
)

# Every class using decorules must set metaclass=HasRulesActions.
# Decorators are applied bottom-up (innermost first).

@raise_if_false_on_class(member_enforcer('SCALE', float, 0.0, operator.gt),
                          AttributeError, "SCALE must be a positive float")
@raise_if_false_on_instance(lambda inst: inst.value >= 0,
                              ValueError, "value must be non-negative")
class Counter(metaclass=HasRulesActions):
    SCALE = 1.0

    def __init__(self, value: int = 0):
        self.value = value

    @run_instance_rules           # re-runs instance rules after each call
    def increment(self, amount: int = 1):
        self.value += amount

c = Counter(5)       # OK
c.increment(3)       # OK
c.increment(-100)    # raises ValueError: value must be non-negative
```

## The five decorators

| Decorator | Applied to | What it does |
|---|---|---|
| `raise_if_false_on_class` | class | Raises an exception at class-definition time if the predicate fails |
| `raise_if_false_on_instance` | class | Raises an exception after `__init__` (and after `@run_instance_rules` methods) if the predicate fails |
| `run_if_false_on_instance` | class | Calls a user-supplied function instead of raising |
| `run_instance_rules` | method | Re-runs all instance rules after the method returns |
| `run_instance_actions` | method | Re-runs all instance actions after the method returns |

All class-level decorators require `metaclass=HasRulesActions`.

## Step-by-step guide

### 1 – Choose your metaclass

Every class governed by decorules must declare `metaclass=HasRulesActions`:

```python
from decorules import HasRulesActions

class MyBase(metaclass=HasRulesActions):
    ...
```

Subclasses inherit this automatically — you only need to set it on the root class.

### 2 – Write a predicate

A **predicate** is a function that returns `True` (rule satisfied) or `False` (rule violated).

* For **class-level** checks the predicate receives the class as its first argument and an optional `attrs` dict as the second (rarely needed; default it to `None`).
* For **instance-level** checks the predicate receives the instance as its only argument.

```python
# Class-level predicate: does the class have a float attribute SCALE?
def has_float_scale(cls_or_instance, attrs=None):
    val = getattr(cls_or_instance, 'SCALE', None)
    return isinstance(val, float)

# Instance-level predicate: is self.value non-negative?
def value_is_non_negative(instance):
    return instance.value >= 0
```

The built-in `member_enforcer` factory covers the common key+type+comparison pattern without you having to write the function yourself (see §3).

### 3 – Use `member_enforcer` for attribute checks

`member_enforcer(key, type, [comparison_value, operator])` returns a ready-made predicate:

```python
import operator
from decorules import member_enforcer

member_enforcer('SCALE', float)                       # SCALE is a float
member_enforcer('SCALE', float, 0.0, operator.gt)     # SCALE is a positive float
member_enforcer('SCALE', float, 2.0, operator.le)     # SCALE is a float <= 2.0
```

### 4 – Apply a class-level rule

Use `@raise_if_false_on_class` to check the **class itself** at definition time.  If the check fails the class is never created:

```python
from decorules import HasRulesActions, raise_if_false_on_class, member_enforcer
import types

@raise_if_false_on_class(member_enforcer('process', types.FunctionType),
                          AttributeError, "process() method is required")
class MyBase(metaclass=HasRulesActions):
    def process(self):
        return 42
```

Any subclass that removes `process` will raise `AttributeError` at *definition* time.

### 5 – Apply an instance-level rule

Use `@raise_if_false_on_instance` to validate **instances** after `__init__`:

```python
from decorules import HasRulesActions, raise_if_false_on_instance

@raise_if_false_on_instance(lambda inst: isinstance(inst.x, int), AttributeError)
class HasIntX(metaclass=HasRulesActions):
    def __init__(self, value=20):
        self.x = value

a = HasIntX()     # OK
b = HasIntX(25)   # OK
```

To re-run the check after a mutating method, add `@run_instance_rules`:

```python
from decorules import run_instance_rules

@raise_if_false_on_instance(lambda inst: inst.y < 10, ValueError)
class BoundedCounter(metaclass=HasRulesActions):
    def __init__(self, value=0):
        self.y = value

    @run_instance_rules     # ValueError raised here if y >= 10 after the call
    def add(self, amount=1):
        self.y += amount

a = BoundedCounter(0)
a.add(1)   # y=1  – OK
a.add(10)  # y=11 – raises ValueError
```

### 6 – Trigger an action instead of raising

Use `@run_if_false_on_instance` when you want to *react* to a condition without crashing.  The action function receives the instance:

```python
from decorules import HasRulesActions, run_if_false_on_instance, run_instance_actions

audit_log = []

def record_overflow(instance):
    audit_log.append(instance.value)

@run_if_false_on_instance(lambda inst: inst.value < 100, record_overflow)
class ManagedInt(metaclass=HasRulesActions):
    def __init__(self, value: int = 0):
        self.value = value

    @run_instance_actions   # actions fire after each call
    def set(self, new_value: int):
        self.value = new_value

m = ManagedInt(50)
m.set(80)    # below 100 – nothing logged
m.set(120)   # >= 100  – record_overflow called, audit_log == [120]
```

### 7 – Stacking multiple decorators

Decorators are applied bottom-up (the decorator closest to the class is applied first).  You can combine as many as you like:

```python
import operator, types
from decorules import (HasRulesActions, raise_if_false_on_class,
                        raise_if_false_on_instance, member_enforcer)

@raise_if_false_on_instance(lambda inst: sum(x**2 for x in inst.coords)**0.5 <= 1.0,
                              ValueError, "coordinates outside unit sphere")
@raise_if_false_on_class(member_enforcer('MULTIPLIER', float, 1.0, operator.gt),
                          AttributeError, "MULTIPLIER must be > 1.0")
@raise_if_false_on_class(member_enforcer('process', types.FunctionType),
                          AttributeError, "process() method required")
class PhysicsObject(metaclass=HasRulesActions):
    MULTIPLIER = 2.0

    def __init__(self, *coords):
        self.coords = list(coords)

    def process(self):
        return [c * self.MULTIPLIER for c in self.coords]
```

## Examples

A fully worked example of library/client class hierarchies lives in `src/example/`:

* `library_class.py` – the library author's base class with enforced rules.
* `client_class.py` – client code that inherits from the library class and adds further rules.

The test suite in `tests/test_decs.py` contains many more patterns, including interaction with `@dataclass` and `@property`.

## Advanced: transferring rules

The `EnforcedFunctions` registry stores all registered functions and is accessible at runtime:

```python
from decorules import EnforcedFunctions

# Get plain boolean predicates for all registered classes
class_checks, instance_checks = EnforcedFunctions.revert_to_boolean_returns()
```

---

[^1]: The functionality for actions is entirely user-defined. Common uses: callbacks, logging, asynchronous tasks, and side-effects.
[^2]: By default, rules and actions on instances are enforced only after construction. Use `@run_instance_rules` / `@run_instance_actions` on any mutating method to re-enforce them after each call.
[^3]: The `@dataclass` and `@property` decorators interact with decorules – see `tests/test_decs.py` for examples.
[^4]: For class-level predicates that check attribute *values*, accept an optional `attrs: dict = None` second parameter. This allows the same predicate to work on both class and instance.
[^5]: `exception_type` must be an exception class whose constructor accepts a single string argument. Defaults: `AttributeError` for class rules, `ValueError` for instance rules.
[^6]: `member_enforcer` signature: `member_enforcer(key, type, [comparison_value, operator_used, attrs_used])`. Operator defaults to `operator.eq` and is only applied when `comparison_value` is supplied.
[^7]: The `action` function passed to `run_if_false_on_instance` receives the instance. Use `functools.partial` to pre-bind extra arguments.
