"""An append-only decision log for the policy registry (v0.25).

The registry (v0.24) holds the policies; this log holds the **history of choosing
between them**. Adopting a policy appends one typed, clock-free record -- a
sequence number, the policy name and a content hash of its profile, the base it
replaced, the stated reason, and a tuning-impact summary -- to ``decisions.jsonl``
in the registry directory. The log is:

- **clock-free**: no timestamps, so the file is deterministic and diffable, and a
  replayed adoption produces byte-identical bytes;
- **append-only and hash-chained**: each entry carries the previous entry's hash,
  so a removed or reordered entry breaks the chain and is caught;
- **content-anchored**: each entry pins the adopted profile's hash, so a policy
  file silently swapped *after* adoption is detected (the registry file no longer
  matches what was adopted).

Nothing here changes any verdict; it records which policy a project chose to run.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from littleboy.rules.policy import (
    NamedPolicy,
    PolicyProfile,
    registry_dir,
    verify_named_policy,
)

DECISION_LOG_NAME = "decisions.jsonl"
_GENESIS = "0" * 64  # the previous-hash of the very first entry


def profile_hash(profile: PolicyProfile) -> str:
    """A stable content hash of a policy profile (canonical JSON, sha256).

    Keys are sorted and separators are fixed, so the hash depends only on the
    profile's values -- never on field order or formatting.
    """
    canonical = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DecisionEntry(BaseModel):
    """One adoption, recorded append-only. Clock-free and hash-chained."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=0, description="0-based position in the log.")
    policy_name: str
    profile_hash: str = Field(description="sha256 of the adopted profile at adoption time.")
    base: str = Field(default="", description="The built-in the adopted policy derived from.")
    replaced: str = Field(
        default="", description="The policy in force before this adoption ('' if none)."
    )
    reason: str = ""
    forced: bool = Field(
        default=False, description="True if a flagged policy was adopted anyway (--force)."
    )
    flags_at_adoption: list[str] = Field(
        default_factory=list, description="Provenance problems present when adopted (if forced)."
    )
    impact_summary: dict[str, object] = Field(
        default_factory=dict, description="A small, stable digest of the tuning impact, if given."
    )
    prev_hash: str = Field(description="sha256 of the previous entry's canonical line (chain).")


def _entry_payload(entry: DecisionEntry) -> dict:
    """The chained content of an entry: everything except the chain pointer itself."""
    data = entry.model_dump(mode="json")
    data.pop("prev_hash")
    return data


def entry_hash(entry: DecisionEntry) -> str:
    """The hash an entry contributes to the chain (its content, excluding ``prev_hash``)."""
    canonical = json.dumps(_entry_payload(entry), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def decision_log_path(directory: str | Path | None = None) -> Path:
    """Path to ``decisions.jsonl`` in the registry directory."""
    return registry_dir(directory) / DECISION_LOG_NAME


def read_decision_log(directory: str | Path | None = None) -> list[DecisionEntry]:
    """Read every decision entry in order (``[]`` if the log does not exist)."""
    path = decision_log_path(directory)
    if not path.is_file():
        return []
    entries: list[DecisionEntry] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            entries.append(DecisionEntry.model_validate_json(line))
    return entries


def current_policy(directory: str | Path | None = None) -> DecisionEntry | None:
    """The most recent adoption -- the project's working policy -- or ``None``."""
    log = read_decision_log(directory)
    return log[-1] if log else None


def _impact_digest(impact: dict | None) -> dict[str, object]:
    """A small, stable digest of a tuning-impact dict (clock-free, no per-case noise)."""
    if not impact:
        return {}
    keep = ("base_policy", "n_cases", "n_flips", "flip_summary", "net_deltas")
    return {k: impact[k] for k in keep if k in impact}


def append_decision(
    named: NamedPolicy,
    *,
    directory: str | Path | None = None,
    reason: str = "",
    impact: dict | None = None,
    force: bool = False,
) -> DecisionEntry:
    """Append one adoption to the log, refusing a flagged policy unless ``force``.

    Returns the appended :class:`DecisionEntry`. A flagged policy (tampered
    provenance) raises ``ValueError`` unless ``force=True``, in which case the
    entry records ``forced=True`` and the flags present at adoption -- the
    override is logged, never silent.
    """
    check = verify_named_policy(named)
    flags = [] if check.consistent else list(check.problems)
    if flags and not force:
        raise ValueError(
            f"refusing to adopt '{named.name}': its provenance is inconsistent "
            f"({'; '.join(flags)}); pass force=True to adopt anyway (it will be logged)"
        )

    log = read_decision_log(directory)
    prev = log[-1] if log else None
    entry = DecisionEntry(
        seq=len(log),
        policy_name=named.name,
        profile_hash=profile_hash(named.profile),
        base=named.provenance.base if named.provenance else "",
        replaced=prev.policy_name if prev else "",
        reason=reason,
        forced=bool(flags),
        flags_at_adoption=flags,
        impact_summary=_impact_digest(impact),
        prev_hash=entry_hash(prev) if prev else _GENESIS,
    )
    path = decision_log_path(directory)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(entry.model_dump(mode="json"), ensure_ascii=False)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")
    return entry


class DecisionLogReport(BaseModel):
    """A verified reading of the decision log: the chain, and each entry vs the registry."""

    model_config = ConfigDict(extra="forbid")

    directory: str
    exists: bool = True
    n_entries: int = 0
    entries: list[DecisionEntry] = Field(default_factory=list)
    current: str = Field(default="", description="The currently adopted policy name ('' if none).")
    chain_intact: bool = True
    n_problems: int = 0
    problems: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def verify_decision_log(directory: str | Path | None = None) -> DecisionLogReport:
    """Verify the chain and re-check each adoption against the current registry files.

    Two integrity checks: the **hash chain** (each entry's ``prev_hash`` must equal
    the prior entry's content hash, and sequence numbers must be contiguous), and
    **content drift** (the adopted ``profile_hash`` must still match the registry
    file that currently carries that name -- a silently swapped file after
    adoption is exactly what this catches). Missing-from-registry is reported, not
    treated as drift.
    """
    d = registry_dir(directory)
    path = decision_log_path(directory)
    if not path.is_file():
        return DecisionLogReport(
            directory=str(d),
            exists=False,
            notes=[f"no decision log at {path}; adopt a policy to start one"],
        )

    entries = read_decision_log(directory)
    problems: list[str] = []

    # 1. the hash chain
    chain_intact = True
    expected_prev = _GENESIS
    for i, entry in enumerate(entries):
        if entry.seq != i:
            chain_intact = False
            problems.append(f"entry {i}: seq is {entry.seq}, expected {i} (reordered or removed)")
        if entry.prev_hash != expected_prev:
            chain_intact = False
            problems.append(
                f"entry {i} ('{entry.policy_name}'): broken chain -- prev_hash does not match "
                "the prior entry (an entry was altered, removed, or reordered)"
            )
        expected_prev = entry_hash(entry)

    # 2. content drift vs the current registry (lazy import avoids a cycle)
    from littleboy.rules.policy import _registry_files, load_named_policy

    by_name: dict[str, str] = {}
    if d.is_dir():
        for file in _registry_files(d):
            try:
                named = load_named_policy(file)
            except Exception:  # noqa: BLE001 - unreadable files cannot anchor a hash
                continue
            by_name[named.name] = profile_hash(named.profile)

    current = entries[-1].policy_name if entries else ""
    current_hash = by_name.get(current)
    if entries:
        if current not in by_name:
            problems.append(
                f"current policy '{current}' is not in the registry {d} -- the adopted file "
                "is missing (renamed or deleted since adoption)"
            )
        elif current_hash != entries[-1].profile_hash:
            problems.append(
                f"current policy '{current}' has DRIFTED: the registry file no longer matches "
                "the profile that was adopted (a silent swap after adoption)"
            )

    notes = [
        "the hash chain catches altered/removed/reordered entries; the content check catches "
        "a registry file swapped after adoption",
        "clock-free: the log carries no timestamps, so it stays deterministic and diffable",
    ]
    return DecisionLogReport(
        directory=str(d),
        n_entries=len(entries),
        entries=entries,
        current=current,
        chain_intact=chain_intact,
        n_problems=len(problems),
        problems=problems,
        notes=notes,
    )
