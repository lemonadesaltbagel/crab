"""CRAB was called Teardown before 0.4. ``import teardown...``, and saved specs such as
``fake:py:teardown.examples...``, keep working for this release: every ``teardown.<module>`` is the corresponding
``crab.<module>``."""

from __future__ import annotations

import importlib
import importlib.abc
import importlib.util
import sys


class _Alias(importlib.abc.MetaPathFinder, importlib.abc.Loader):
    def find_spec(self, name, path=None, target=None):
        if not name.startswith("teardown."):
            return None
        return importlib.util.spec_from_loader(name, self)

    def create_module(self, spec):
        return importlib.import_module("crab" + spec.name[len("teardown"):])

    def exec_module(self, module):
        pass  # the crab module is already executed


if not any(isinstance(f, _Alias) for f in sys.meta_path):
    sys.meta_path.insert(0, _Alias())


def __getattr__(name: str):
    return getattr(importlib.import_module("crab"), name)
