"""Where CRAB's non-Python files and its local state live.

Running from a source checkout, both are the checkout: room images build from the repository, and verification
links go under its `.crab/`. Installed from a wheel, the package carries the room files (`_room/`). The same
build context is assembled once per version under the user's CRAB directory (`CRAB_HOME`, default
`~/.crab`), so the unchanged Dockerfiles and compose files work from an installed copy too.

CRAB was called Teardown before 0.4: `TEARDOWN_*` variables and an existing `~/.teardown` (or a checkout's
`.teardown/`) are still used when no CRAB one is set or exists.
"""

from __future__ import annotations

import os
import shutil
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

DIST = "crab-cleanroom"  # the distribution on PyPI (the import package and the command are `crab`)
PACKAGE = Path(__file__).resolve().parent
CHECKOUT = PACKAGE.parents[1]


def in_checkout() -> bool:
    return (CHECKOUT / "pyproject.toml").is_file() and (CHECKOUT / "deploy" / "cleanroom.yaml").is_file() \
        and (CHECKOUT / "src" / "crab").is_dir()


def env(name: str, default: str | None = None) -> str | None:
    """``CRAB_<name>``, else the pre-0.4 ``TEARDOWN_<name>``, else ``default``."""
    for prefix in ("CRAB_", "TEARDOWN_"):
        value = os.environ.get(prefix + name)
        if value is not None:
            return value
    return default


def _new_or_existing_old(new: Path, old: Path) -> Path:
    return old if old.exists() and not new.exists() else new


def cache_dir() -> Path:
    """Downloaded and generated files that can be rebuilt (browser assets, busybox, the Android signing key)."""
    if env("CACHE"):
        return Path(env("CACHE"))
    return _new_or_existing_old(Path.home() / ".cache" / "crab", Path.home() / ".cache" / "teardown")


def state_dir() -> Path:
    """Local runtime state (verification links, assembled room contexts)."""
    if in_checkout():
        return _new_or_existing_old(CHECKOUT / ".crab", CHECKOUT / ".teardown")
    if env("HOME"):
        return Path(env("HOME"))
    return _new_or_existing_old(Path.home() / ".crab", Path.home() / ".teardown")


def room_root() -> Path:
    """The build context of the room images: the checkout, or one assembled from the installed package."""
    if in_checkout():
        return CHECKOUT
    try:
        current = version(DIST)
    except PackageNotFoundError:  # pragma: no cover - an unpackaged, non-checkout copy
        current = "local"
    root = state_dir() / "room" / current
    if (root / ".complete").exists():
        return root
    shipped = PACKAGE / "_room"
    if not shipped.is_dir():
        raise FileNotFoundError("this CRAB installation does not include the room files (crab/_room)")
    tmp = root.with_name(root.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.copytree(shipped, tmp)  # pyproject.toml, README.md, LICENSE, NOTICE, deploy/
    shutil.copytree(PACKAGE, tmp / "src" / "crab",
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "_room", "observer-playbook.md"))
    (tmp / "docs").mkdir(exist_ok=True)
    shutil.copy2(PACKAGE / "observer-playbook.md", tmp / "docs" / "observer-playbook.md")
    (tmp / ".complete").write_text(current, encoding="utf-8")
    shutil.rmtree(root, ignore_errors=True)
    tmp.rename(root)
    return root
