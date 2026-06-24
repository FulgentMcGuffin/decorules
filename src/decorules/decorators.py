"""
Public decorators for enforcing rules and triggering actions on classes and instances.

These are the main entry points for library authors using decorules.

Class decorators
----------------
``raise_if_false_on_class``
    Raise an exception if a class-level predicate fails at definition time.
``raise_if_false_on_instance``
    Raise an exception if an instance-level predicate fails after construction.
``run_if_false_on_instance``
    Call a user-supplied function when an instance-level predicate fails.

Method decorators
-----------------
``run_instance_rules``
    Re-run all registered instance *rules* after the decorated method returns.
``run_instance_actions``
    Re-run all registered instance *actions* after the decorated method returns.
"""

from collections.abc import Callable
from functools import wraps, partial

from decorules.has_rules_actions import HasRulesActions, EnforcedFunctions
from decorules.utils import Purpose


def _raise_exception(exception_type: type[BaseException], message: str) -> None:
    """Construct and raise *exception_type* with *message*."""
    raise exception_type(message)


def _make_enforcement_decorator(
    predicate: Callable[..., bool],
    on_failure: Callable,
    on_class: bool = True,
    extra_info: str = "",
    purpose: Purpose = Purpose.RULE,
) -> Callable:
    """
    Core factory used internally by all public decorators.

    Returns a class decorator that:

    * For class-level checks (``on_class=True``): runs the predicate
      immediately at class definition and stores the check for introspection.
    * For instance-level checks (``on_class=False``): registers the predicate
      to run at every instance creation (and after any method that is itself
      decorated with ``run_instance_rules`` / ``run_instance_actions``).

    Parameters
    ----------
    predicate :
        The boolean predicate to enforce.
    on_failure :
        Callable invoked when *predicate* returns ``False``.  Receives an
        error-message string for rules, or the instance for actions.
    on_class :
        ``True`` for class-level checks, ``False`` for instance-level.
    extra_info :
        Text prepended to the rule failure message.
    purpose :
        ``Purpose.RULE`` or ``Purpose.ACTION``.
    """
    predicate_label = str(predicate)

    def _make_check(decorated_cls: type) -> Callable:
        """Wrap *predicate* into a check+act function closed over *decorated_cls*."""

        @wraps(predicate)
        def _check(*args, **kwargs) -> None:
            if on_class and len(args) > 1:
                # When called via run_functions_applied_to_class the class
                # namespace dict may arrive as a second positional argument.
                dict_args = [a for a in args if isinstance(a, dict)]
                if len(dict_args) > 1:
                    raise ValueError(
                        "Enforcement function received more than one dict argument "
                        "(only one is allowed, for class namespace attrs)."
                    )
                if dict_args:  # only re-pack if a dict was actually present
                    kwargs["attrs"] = dict_args[0]
                    args = tuple(a for a in args if a is not dict_args[0])

            if predicate(*args, **kwargs) is False:
                if purpose is Purpose.RULE:
                    scope = "class" if on_class else "instance"
                    # BUG FIX: use decorated_cls.__name__ (the class being
                    # decorated), not decorated_cls.__class__.__name__ which
                    # gives the metaclass name (HasRulesActions).
                    msg = (
                        f"{extra_info} {decorated_cls.__name__} "
                        f"fails {scope} check {predicate_label}"
                    ).strip()
                    on_failure(msg)
                elif purpose is Purpose.ACTION:
                    on_failure(args[0])  # args[0] is the instance (not the metaclass)

        return _check

    if on_class:
        def _class_decorator(cls: type) -> type:
            if not issubclass(type(cls), HasRulesActions):
                raise TypeError(
                    f"'{cls.__name__}' must use HasRulesActions as its metaclass "
                    f"to use a class-level decorules decorator."
                )
            check = _make_check(cls)
            EnforcedFunctions.add_enforce_function_to_class(cls.__name__, check)
            check(cls)  # Run immediately at class-definition time.
            return cls

        return _class_decorator

    else:
        def _instance_decorator(cls: type) -> type:
            if not issubclass(type(cls), HasRulesActions):
                raise TypeError(
                    f"'{cls.__name__}' must use HasRulesActions as its metaclass "
                    f"to use an instance-level decorules decorator."
                )
            # Registered here; executed on every instance creation (see HasRulesActions.__call__).
            EnforcedFunctions.add_enforce_function_to_instance(
                cls.__name__, _make_check(cls), purpose
            )
            return cls

        return _instance_decorator


# ---------------------------------------------------------------------------
# Public class decorators
# ---------------------------------------------------------------------------


def raise_if_false_on_class(
    predicate: Callable[..., bool],
    exception_type: type[BaseException] = AttributeError,
    extra_info: str | None = None,
) -> Callable:
    """
    Class decorator: raise *exception_type* if *predicate* returns ``False``
    when the **class is defined**.

    Use this to enforce that a class (and every subclass) always has certain
    attributes or methods.  The check fires once at decoration time; if the
    class fails it is never created.

    Parameters
    ----------
    predicate : callable
        ``(cls_or_instance, attrs=None) -> bool``.  Return ``False`` to
        trigger the exception.  *attrs* is an optional class-namespace dict.
    exception_type : type[BaseException], optional
        Exception class to raise on failure.  Defaults to ``AttributeError``.
    extra_info : str, optional
        Text prepended to the exception message.

    Examples
    --------
    Require every subclass to define a ``float`` attribute ``SCALE``::

        from decorules import HasRulesActions, raise_if_false_on_class, member_enforcer

        @raise_if_false_on_class(member_enforcer('SCALE', float),
                                  AttributeError, "SCALE must be a float")
        class MyBase(metaclass=HasRulesActions):
            SCALE = 1.0
    """
    return _make_enforcement_decorator(
        predicate,
        partial(_raise_exception, exception_type),
        on_class=True,
        extra_info=extra_info or "",
        purpose=Purpose.RULE,
    )


def raise_if_false_on_instance(
    predicate: Callable[[object], bool],
    exception_type: type[BaseException] = ValueError,
    extra_info: str | None = None,
) -> Callable:
    """
    Class decorator: raise *exception_type* if *predicate* returns ``False``
    when an **instance is created** (and after any method tagged with
    ``@run_instance_rules``).

    Parameters
    ----------
    predicate : callable
        ``(instance) -> bool``.  Return ``False`` to trigger the exception.
    exception_type : type[BaseException], optional
        Exception class to raise on failure.  Defaults to ``ValueError``.
    extra_info : str, optional
        Text prepended to the exception message.

    Examples
    --------
    Require every instance to have a non-negative ``value``::

        @raise_if_false_on_instance(lambda inst: inst.value >= 0,
                                     ValueError, "value must be >= 0")
        class Counter(metaclass=HasRulesActions):
            def __init__(self, value: int = 0):
                self.value = value
    """
    # Note: do NOT write exception_type=exception_type inside the partial call –
    # it would shadow the outer parameter and confuse Python's name resolution.
    return _make_enforcement_decorator(
        predicate,
        partial(_raise_exception, exception_type),
        on_class=False,
        extra_info=extra_info or "",
        purpose=Purpose.RULE,
    )


def run_if_false_on_instance(
    predicate: Callable[[object], bool],
    action: Callable[[object], None],
) -> Callable:
    """
    Class decorator: call *action* with the instance when *predicate* returns
    ``False`` (i.e. when the condition is **not** met).

    Unlike ``raise_if_false_on_instance``, this does not raise an exception –
    it runs user-supplied logic such as callbacks, logging, or side-effects.

    Parameters
    ----------
    predicate : callable
        ``(instance) -> bool``.  Return ``False`` to trigger *action*.
    action : callable
        ``(instance) -> None``.  Called when *predicate* is ``False``.
        Extra arguments can be pre-bound with ``functools.partial``.

    Examples
    --------
    Log every instance whose counter exceeds a threshold::

        def log_large(instance):
            print(f"Large value: {instance.value}")

        @run_if_false_on_instance(lambda inst: inst.value < 100, log_large)
        class Counter(metaclass=HasRulesActions):
            def __init__(self, value: int = 0):
                self.value = value
    """
    return _make_enforcement_decorator(
        predicate,
        action,
        on_class=False,
        extra_info="",
        purpose=Purpose.ACTION,
    )


# ---------------------------------------------------------------------------
# Public method decorators
# ---------------------------------------------------------------------------


def run_instance_rules(method: Callable) -> Callable:
    """
    Method decorator: re-run all registered instance *rules* after the method
    returns.

    Without this decorator, instance rules are only checked at construction
    time.  Add ``@run_instance_rules`` to any mutating method to guarantee
    that all rules remain satisfied after each call.

    Examples
    --------
    ::

        class Counter(metaclass=HasRulesActions):
            def __init__(self, value: int = 0):
                self.value = value

            @run_instance_rules   # checks rules after every call
            def increment(self, amount: int = 1):
                self.value += amount
    """
    @wraps(method)
    def _wrapper(self, *args, **kwargs):
        method(self, *args, **kwargs)
        EnforcedFunctions.run_functions_applied_to_instance(self, Purpose.RULE)

    return _wrapper


def run_instance_actions(method: Callable) -> Callable:
    """
    Method decorator: re-run all registered instance *actions* after the
    method returns.

    Mirrors ``run_instance_rules`` but for actions registered with
    ``run_if_false_on_instance``.

    Examples
    --------
    Combine with ``run_instance_rules`` to trigger both rules and actions::

        @run_instance_actions   # actions fire after the call
        @run_instance_rules     # rules are also checked after the call
        def update(self, new_value: int):
            self.value = new_value
    """
    @wraps(method)
    def _wrapper(self, *args, **kwargs):
        method(self, *args, **kwargs)
        EnforcedFunctions.run_functions_applied_to_instance(self, Purpose.ACTION)

    return _wrapper
