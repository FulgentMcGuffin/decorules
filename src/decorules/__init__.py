"""
decorules – enforce class structure and instance behaviour through decorators.

Quick start
-----------
Every class governed by decorules must use ``HasRulesActions`` as its
metaclass.  Then stack the decorator(s) you need on top::

    import operator
    from decorules import (
        HasRulesActions,
        raise_if_false_on_class,
        raise_if_false_on_instance,
        run_instance_rules,
        member_enforcer,
    )

    @raise_if_false_on_class(member_enforcer('SCALE', float, 0.0, operator.gt),
                              AttributeError, "SCALE must be a positive float")
    @raise_if_false_on_instance(lambda inst: inst.value >= 0,
                                 ValueError, "value must be non-negative")
    class MyBase(metaclass=HasRulesActions):
        SCALE = 1.0

        def __init__(self, value: int = 0):
            self.value = value

        @run_instance_rules       # re-checks rules after every call
        def increment(self, amount: int = 1):
            self.value += amount

The five main decorators
------------------------
* ``raise_if_false_on_class``    – raise if a **class-level** predicate fails.
* ``raise_if_false_on_instance`` – raise if an **instance-level** predicate fails.
* ``run_if_false_on_instance``   – call a function if an instance predicate fails.
* ``run_instance_rules``         – method decorator: re-run instance rules after each call.
* ``run_instance_actions``       – method decorator: re-run instance actions after each call.
"""

from decorules.decorators import (
    raise_if_false_on_class,
    raise_if_false_on_instance,
    run_if_false_on_instance,
    run_instance_rules,
    run_instance_actions,
)
from decorules.has_rules_actions import HasRulesActions, EnforcedFunctions
from decorules.utils import Purpose, member_enforcer

__all__ = [
    # Metaclass — required on every class that uses decorules
    "HasRulesActions",
    # Class-level decorator
    "raise_if_false_on_class",
    # Instance-level decorators
    "raise_if_false_on_instance",
    "run_if_false_on_instance",
    # Method decorators
    "run_instance_rules",
    "run_instance_actions",
    # Built-in predicate factory
    "member_enforcer",
    # Enum used when Purpose needs to be referenced directly
    "Purpose",
    # Advanced: global function registry
    "EnforcedFunctions",
]
