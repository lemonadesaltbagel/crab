"""CRAB was Teardown before 0.4: the old command, variables, directories and import paths keep working."""

from __future__ import annotations

import pytest


def test_old_variables_are_read_when_no_crab_one_is_set(monkeypatch):
    from crab.resources import env

    monkeypatch.delenv("CRAB_MAX_CALL_S", raising=False)
    monkeypatch.setenv("TEARDOWN_MAX_CALL_S", "120")
    assert env("MAX_CALL_S", "200") == "120"
    monkeypatch.setenv("CRAB_MAX_CALL_S", "90")
    assert env("MAX_CALL_S", "200") == "90"  # the new name wins
    monkeypatch.delenv("CRAB_MAX_CALL_S")
    monkeypatch.delenv("TEARDOWN_MAX_CALL_S")
    assert env("MAX_CALL_S", "200") == "200"


def test_an_existing_teardown_home_is_kept_until_a_crab_one_exists(monkeypatch, tmp_path):
    from crab import resources

    monkeypatch.setattr(resources, "in_checkout", lambda: False)
    for name in ("CRAB_HOME", "TEARDOWN_HOME", "CRAB_CACHE", "TEARDOWN_CACHE"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert resources.state_dir() == tmp_path / ".crab"  # a new user
    (tmp_path / ".teardown").mkdir()
    (tmp_path / ".cache" / "teardown").mkdir(parents=True)
    assert resources.state_dir() == tmp_path / ".teardown"  # an existing one keeps their state
    assert resources.cache_dir() == tmp_path / ".cache" / "teardown"
    (tmp_path / ".crab").mkdir()
    assert resources.state_dir() == tmp_path / ".crab"


def test_old_import_paths_are_the_crab_modules():
    import teardown.drivers.web.driver as old

    import crab.drivers.web.driver as new
    from crab.drivers.fake import open_fake

    assert old is new
    clone = open_fake("fake:py:teardown.examples.signup_clone:BuggySignup")  # a spec saved before the rename
    assert type(clone).__module__.startswith("crab.")


def test_the_old_command_still_runs_and_says_what_changed(capsys):
    from crab.cli import legacy_main

    with pytest.raises(SystemExit) as done:
        import sys

        sys.argv = ["teardown", "--version"]
        legacy_main()
    assert done.value.code == 0
    out = capsys.readouterr()
    assert "Teardown is now CRAB" in out.err and out.out.startswith("crab ")


def test_an_apk_older_than_its_sources_is_rebuilt(tmp_path):
    """After the rename the cached agent was still the old package, and the driver waited for the new one."""
    import os

    from crab.drivers.android.driver import stale

    src = tmp_path / "agent"
    (src / "build").mkdir(parents=True)
    (src / "AndroidManifest.xml").write_text("<manifest package='dev.crab.agent'/>")
    apk = src / "build" / "agent.apk"
    assert stale(apk, src)  # never built
    apk.write_bytes(b"apk")
    os.utime(src / "AndroidManifest.xml", (1, 1))
    assert not stale(apk, src)
    (src / "build" / "intermediate.dex").write_bytes(b"x")  # build output is not a source
    assert not stale(apk, src)
    os.utime(src / "AndroidManifest.xml", None)
    os.utime(apk, (1, 1))
    assert stale(apk, src)  # the manifest changed after the build
