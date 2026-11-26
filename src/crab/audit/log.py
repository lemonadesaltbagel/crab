"""Append-only, hash-chained audit log of in-toto v1 statements.

Each line is ``{"seq", "prev", "statement", "digest"}`` where ``digest = sha256(canonical(seq, prev, statement))``.
Editing, removing or reordering any line breaks :meth:`AuditLog.verify`. DSSE signing and external checkpoint
anchoring (RFC 3161 / Rekor) come in Phase 3; the chain format does not change.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - Windows has no flock; appends are still serialized per process
    fcntl = None  # type: ignore[assignment]

from crab.core.ids import canonical_json, sha256_hex

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_BASE = "https://github.com/lemonadesaltbagel/crab/attestation"
GENESIS = "0" * 64


class AuditChainBroken(ValueError):
    pass


def predicate_type(name: str) -> str:
    return f"{PREDICATE_BASE}/{name}/v0.1"


class AuditLog:
    """``signer`` (optional) wraps every statement in a DSSE envelope; the chain digest covers the envelope."""

    def __init__(self, path: str | Path, signer=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.signer = signer
        # The chain tail and the line that extends it must be one step. The thread lock covers threads; the
        # sidecar flock covers the gate, the observer and CLI commands, which may run as separate processes on
        # the same project (see docs/clean-runtime.md).
        self._lock_path = self.path.with_name(f"{self.path.name}.lock")
        self._thread_lock = threading.Lock()

    @contextmanager
    def _append_lock(self) -> Iterator[None]:
        with self._thread_lock, self._lock_path.open("a") as lock_file:
            if fcntl is not None:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

    def append(self, predicate: str, subjects: dict[str, str | list[str]], body: dict[str, Any]) -> dict[str, Any]:
        """``subjects`` maps a name to its sha256 hex digest (ids are converted by stripping their prefix), or to a
        list of them (recorded as ``name[0]``, ``name[1]``, ...)."""
        with self._append_lock():
            seq, prev = self._tail()
            flat: list[tuple[str, str]] = []
            for name, digest in sorted(subjects.items()):
                if isinstance(digest, list | tuple):
                    flat.extend((f"{name}[{i}]", d) for i, d in enumerate(digest))
                else:
                    flat.append((name, digest))
            statement = {
                "_type": STATEMENT_TYPE,
                "subject": [{"name": n, "digest": {"sha256": _hex(d)}} for n, d in flat],
                "predicateType": predicate_type(predicate),
                "predicate": body,
            }
            entry: dict[str, Any] = {"seq": seq, "prev": prev, "statement": statement}
            if self.signer is not None:
                entry["dsse"] = self.signer.envelope(canonical_json(statement))
            entry["digest"] = sha256_hex(canonical_json(entry))
            with self.path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
            return entry

    def entries(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def verify(self, public_keys: dict[str, bytes] | None = None) -> int:
        """Check the whole chain (and, given public keys, every DSSE signature); return the number of entries."""
        from crab.audit.signing import verify_envelope

        prev = GENESIS
        entries = self.entries()
        for i, entry in enumerate(entries):
            body = {k: entry[k] for k in ("seq", "prev", "statement", "dsse") if k in entry}
            if entry["seq"] != i or entry["prev"] != prev or sha256_hex(canonical_json(body)) != entry["digest"]:
                raise AuditChainBroken(f"audit chain broken at entry {i}")
            if public_keys is not None:
                if "dsse" not in entry:
                    raise AuditChainBroken(f"entry {i} is not signed")
                try:
                    payload = verify_envelope(entry["dsse"], public_keys)
                except Exception as exc:  # noqa: BLE001 - any verification failure breaks the chain
                    raise AuditChainBroken(f"bad signature on entry {i}: {exc}") from exc
                if payload != canonical_json(entry["statement"]):
                    raise AuditChainBroken(f"signed payload of entry {i} differs from its statement")
            prev = entry["digest"]
        return len(entries)

    def _tail(self) -> tuple[int, str]:
        entries = self.entries()
        return (len(entries), entries[-1]["digest"]) if entries else (0, GENESIS)


def _hex(digest_or_id: str) -> str:
    return digest_or_id.rsplit("_", 1)[-1]
