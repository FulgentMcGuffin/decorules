"""
Built-in predicate helpers for common enforcement checks.

These functions are ready to use with the decorules decorators, or serve as
templates for writing your own predicates.

Each function here is designed to be partially applied with ``functools.partial``
so that it becomes a single-argument predicate ``(instance_or_type) -> bool``
suitable for the decorators.

Note: these helpers are defined at module level (not inside pytest fixtures)
because they are stored in a class-level container and must persist for the
lifetime of the process.
"""

from collections import Counter
from collections.abc import Iterable


def key_type_enforcer(
    instance_or_type,
    enforced_type: type,
    enforced_key: str,
    attrs: dict | None = None,
) -> bool:
    """
    Return ``True`` if *instance_or_type* has an attribute *enforced_key* that
    is an instance of *enforced_type*.

    Designed to be used via ``functools.partial``::

        from functools import partial
        import types

        has_process = partial(key_type_enforcer,
                              enforced_type=types.FunctionType,
                              enforced_key='process')

        @raise_if_false_on_class(has_process, AttributeError)
        class MyClass(metaclass=HasRulesActions):
            def process(self): ...

    Parameters
    ----------
    instance_or_type :
        The class or instance to inspect.
    enforced_type : type
        Expected type of the attribute.
    enforced_key : str
        Name of the attribute to look up.
    attrs : dict, optional
        Fallback namespace dict used when checking class attributes at
        definition time.
    """
    member = getattr(instance_or_type, enforced_key, None)
    if member is None and attrs is not None:
        member = attrs.get(enforced_key)
    if member is None:
        return False
    return issubclass(type(member), enforced_type)


def min_value(
    instance_or_type,
    enforced_key: str,
    hard_floor,
) -> bool:
    """
    Return ``True`` if *instance_or_type* has a numeric attribute *enforced_key*
    whose value is **strictly greater** than *hard_floor*.

    Parameters
    ----------
    instance_or_type :
        The class or instance to inspect.
    enforced_key : str
        Name of the numeric attribute.
    hard_floor :
        The exclusive lower bound.
    """
    member = getattr(instance_or_type, enforced_key, None)
    if member is None:
        return False
    return member > hard_floor


def min_list_type_counter(
    instance_or_type,
    list_name: str,
    min_counter: Counter,
    attrs: dict | None = None,
) -> bool:
    """
    Return ``True`` if *instance_or_type* has an iterable attribute *list_name*
    whose element-type counts are **at least** those in *min_counter*.

    Parameters
    ----------
    instance_or_type :
        The class or instance to inspect.
    list_name : str
        Name of the iterable attribute.
    min_counter : Counter
        Minimum required counts per type, e.g. ``Counter({str: 1, int: 2})``.
    attrs : dict, optional
        Fallback namespace dict for class-attribute checks.

    Examples
    --------
    Require at least one ``str``, two ``int`` and one ``float`` in ``ITEMS``::

        from functools import partial

        @raise_if_false_on_class(
            partial(min_list_type_counter,
                    list_name='ITEMS',
                    min_counter=Counter({str: 1, int: 2, float: 1})),
            AttributeError)
        class MyClass(metaclass=HasRulesActions):
            ITEMS = ('hello', 1, 2, 3.14)
    """
    member = getattr(instance_or_type, list_name, None)
    if member is None and attrs is not None:
        member = attrs.get(list_name)
    if member is None:
        return False
    if not isinstance(member, Iterable):
        return False
    return Counter(type(x) for x in member) >= min_counter
