"""
Core metaclass and global function registry for decorules.

``HasRulesActions``
    The metaclass that every class governed by decorules must use.  After
    ``__init__`` returns it automatically runs all registered instance-level
    rules and actions.

``EnforcedFunctions``
    Global registry (class-level state) that stores the enforcement functions
    registered by the decorators.  Library users rarely need to interact with
    this directly – the decorators populate it automatically.
"""

from collections import defaultdict
from collections.abc import Callable

from decorules.utils import false_on_raise_else_true, Purpose


def _get_all_base_classes(cls: type) -> set[type]:
    """
    Recursively collect all ancestor types of *cls*.

    Args:
        cls: The class to inspect.

    Returns:
        A set of all ancestor types (does *not* include *cls* itself).
    """
    bases: set[type] = set(cls.__bases__)
    for base in cls.__bases__:
        bases.update(_get_all_base_classes(base))
    return bases


class HasRulesActions(type):
    """
    Metaclass that enables decorules enforcement on a class.

    Every class that uses decorules decorators **must** declare::

        class MyClass(metaclass=HasRulesActions):
            ...

    After ``__init__`` completes, this metaclass automatically runs all
    registered instance-level rules and actions for the new instance.
    """

    def __call__(cls, *args, **kwargs):
        # Create the instance normally via __new__ / __init__.
        instance = super().__call__(*args, **kwargs)
        # We allow derived classes to construct instances however they see fit
        # and enforce all instance-level checks here, after construction.
        # All checks must run on every new instance.
        EnforcedFunctions.run_functions_applied_to_instance(instance, Purpose.RULE)
        EnforcedFunctions.run_functions_applied_to_instance(instance, Purpose.ACTION)
        return instance


class EnforcedFunctions:
    """
    Global registry of enforcement functions populated by the decorators.

    Two registries are maintained as class-level state:

    * ``_functions_applied_to_class`` – functions checked once at class
      definition time (registered by ``raise_if_false_on_class``).
    * ``_functions_applied_to_instance`` – functions checked at every instance
      creation and after any method decorated with ``run_instance_rules`` /
      ``run_instance_actions`` (registered by ``raise_if_false_on_instance``
      and ``run_if_false_on_instance``).

    Each registry maps a class name (``str``) to a ``set`` of
    ``(function, Purpose)`` tuples.
    """

    _functions_applied_to_instance: dict[str, set] = defaultdict(set)
    _functions_applied_to_class: dict[str, set] = defaultdict(set)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @classmethod
    def _run_class_checks(
        cls,
        cls_instance: type,
        attrs: dict | None = None,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        for func, func_purpose in cls._functions_applied_to_class[cls_instance.__name__]:
            if func_purpose is purpose:
                func(cls_instance, attrs)

    @classmethod
    def _run_instance_checks(
        cls,
        instance: object,
        cls_key: str,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        for func, func_purpose in cls._functions_applied_to_instance[cls_key]:
            if func_purpose is purpose:
                func(instance)

    # ------------------------------------------------------------------
    # Registration API  (called by the class-level decorators)
    # ------------------------------------------------------------------

    @classmethod
    def add_enforce_function_to_class(
        cls,
        cls_key: str,
        func: Callable,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        """Register *func* as a class-level enforcement function for *cls_key*."""
        cls._functions_applied_to_class[cls_key].add((func, purpose))

    @classmethod
    def add_enforce_function_to_instance(
        cls,
        cls_key: str,
        func: Callable,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        """Register *func* as an instance-level enforcement function for *cls_key*."""
        cls._functions_applied_to_instance[cls_key].add((func, purpose))

    # ------------------------------------------------------------------
    # Execution API  (called by HasRulesActions and the method decorators)
    # ------------------------------------------------------------------

    @classmethod
    def run_functions_applied_to_class(
        cls,
        cls_instance: type,
        attrs: dict | None = None,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        """
        Run all registered class-level enforcement functions for *cls_instance*.

        Note: base classes are processed individually with their own ``attrs``
        if they are themselves of type ``HasRulesActions``.
        """
        if cls._functions_applied_to_class:
            cls._run_class_checks(cls_instance, attrs, purpose)

    @classmethod
    def run_functions_applied_to_instance(
        cls,
        instance: object,
        purpose: Purpose = Purpose.RULE,
    ) -> None:
        """
        Run all registered instance-level enforcement functions for *instance*.

        Walks the full class hierarchy so that rules defined on base classes are
        also enforced on derived-class instances.

        Raises
        ------
        TypeError
            If *instance*'s class does not use ``HasRulesActions`` as its
            metaclass.
        """
        if not issubclass(type(type(instance)), HasRulesActions):
            raise TypeError(
                f"Cannot run instance checks on {type(instance)!r}: "
                f"its metaclass is not HasRulesActions."
            )
        if not cls._functions_applied_to_instance:
            return
        # for the instance functions we must loop through all the bases
        cls_keys = [type(instance).__name__]
        bases = [
            b.__name__
            for b in _get_all_base_classes(type(instance))
            if issubclass(type(b), HasRulesActions)
        ]
        cls_keys.extend(bases)
        for key in cls_keys:
            cls._run_instance_checks(instance, key, purpose)

    # ------------------------------------------------------------------
    # Introspection API
    # ------------------------------------------------------------------

    @classmethod
    def get_functions_applied_instance(cls, class_name: str) -> set:
        """Return all ``(func, Purpose)`` pairs registered for instances of *class_name*."""
        return cls._functions_applied_to_instance[class_name]

    @classmethod
    def get_functions_applied_class(cls, class_name: str) -> set:
        """Return all ``(func, Purpose)`` pairs registered for the class *class_name*."""
        return cls._functions_applied_to_class[class_name]

    @classmethod
    def revert_to_boolean_returns(
        cls,
        class_names: set[str] | None = None,
    ) -> tuple[dict[str, list], dict[str, list]]:
        """
        Convert stored enforcement functions into plain boolean predicates.

        Returns a ``(class_funcs, instance_funcs)`` tuple.  Each value is a
        dict mapping class names to lists of wrapped functions that return
        ``True`` on success and ``False`` on failure (instead of raising).

        This is intended for advanced use cases such as inspecting or
        transferring rules between classes at runtime.

        Parameters
        ----------
        class_names : set of str, optional
            Restrict output to these class names.  Defaults to all registered
            names.  Note: to cover a full class hierarchy, supply all base
            class names that may have their own rules.

        Returns
        -------
        tuple[dict, dict]
            ``(class_level_predicates, instance_level_predicates)``
        """
        if class_names is None:
            class_names = set(cls._functions_applied_to_class) | set(
                cls._functions_applied_to_instance
            )

        class_funcs = {
            key: [
                false_on_raise_else_true(func)
                for func, func_purpose in cls._functions_applied_to_class[key]
                if func_purpose is Purpose.RULE
            ]
            for key in cls._functions_applied_to_class
            if key in class_names
        }
        instance_funcs = {
            key: [
                false_on_raise_else_true(func)
                for func, func_purpose in cls._functions_applied_to_instance[key]
                if func_purpose is Purpose.RULE
            ]
            for key in cls._functions_applied_to_instance
            if key in class_names
        }
        return class_funcs, instance_funcs
