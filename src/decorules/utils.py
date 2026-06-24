"""
Shared utilities used across the decorules library.

``Purpose``
    Enum that distinguishes *rules* (raise an exception on failure) from
    *actions* (call a user-supplied function on failure).

``member_enforcer``
    Factory that returns a predicate ready to drop into any decorules
    decorator.  It checks that a named attribute exists, is of the right
    type, and optionally satisfies a comparison.

``false_on_raise_else_true``
    Wraps a function so it returns ``True`` on success and ``False`` on any
    exception, instead of raising.  Used internally for ``revert_to_boolean_returns``.
"""

import operator
from collections.abc import Callable
from enum import Enum
from functools import wraps


class Purpose(Enum):
    """Distinguishes *rules* (raise on failure) from *actions* (call a function on failure)."""

    RULE = 1
    ACTION = 2


def member_enforcer(
    enforced_key: str,
    enforced_type: type,
    comparison_value=None,
    operator_used: Callable | None = operator.eq,
    attrs_used: dict | None = None,
) -> Callable[..., bool]:
    """
    Return a predicate that checks whether a named attribute exists, has the
    right type, and (optionally) satisfies a comparison against a fixed value.

    The returned predicate has the signature ``(instance_or_type, attrs=None) -> bool``
    and can be passed directly to any decorules decorator.

    Parameters
    ----------
    enforced_key : str
        Name of the attribute to inspect on the class or instance.
    enforced_type : type
        The attribute's value must be an instance of this type (or a subclass).
    comparison_value : optional
        When provided, the attribute value is compared against this using
        ``operator_used``.  Pass ``None`` (default) to skip the comparison step.
    operator_used : callable, optional
        Two-argument comparison function (default: ``operator.eq`` – equality).
        Examples: ``operator.gt``, ``operator.le``.
        Only applied when *comparison_value* is not ``None``.
    attrs_used : dict, optional
        Fallback dict for looking up the attribute if ``getattr`` returns
        ``None``.  Useful for class-level checks that need to inspect the class
        namespace dictionary.

    Returns
    -------
    Callable[..., bool]
        A predicate ``(instance_or_type, attrs=None) -> bool``.

    Examples
    --------
    Require a ``float`` class attribute called ``SCALE``::

        member_enforcer('SCALE', float)

    Require ``SCALE`` to be a positive ``float`` (strictly greater than 0)::

        member_enforcer('SCALE', float, 0.0, operator.gt)

    Require an instance method called ``process``::

        import types
        member_enforcer('process', types.FunctionType)
    """

    def _check(instance_or_type, attrs: dict | None = None) -> bool:
        member = getattr(instance_or_type, enforced_key, None)
        if member is None and attrs_used is not None:
            member = attrs_used.get(enforced_key)
        if member is None and attrs is not None:
            member = attrs.get(enforced_key)
        if member is None:
            return False
        if not issubclass(type(member), enforced_type):
            return False
        if comparison_value is not None and operator_used is not None:
            return bool(operator_used(member, comparison_value))
        return True

    return _check


def false_on_raise_else_true(func: Callable) -> Callable[..., bool]:
    """
    Wrap *func* so that any exception it raises is silently caught and
    ``False`` is returned; ``True`` is returned when *func* completes without
    raising.

    Used by ``EnforcedFunctions.revert_to_boolean_returns`` to convert
    raise-on-failure enforcement functions into plain boolean predicates.
    """
    # will be used when we 'transfer' enforced rules
    @wraps(func)
    def _wrapper(*args, **kwargs) -> bool:
        try:
            func(*args, **kwargs)
            return True
        except Exception:
            return False

    return _wrapper
