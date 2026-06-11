"""Policy profiles for LittleBoy's rule engine.

A :class:`PolicyProfile` is a bundle of *operational parameters* — thresholds and
toggles — that control how strict the rule engine is. Policies change how the
axioms are applied to uncertain, real-world data; they never change the axioms
themselves.

These numbers are deliberate, documented defaults, **not** claims of absolute
moral truth. They exist so that the same case can be examined under different
risk postures (e.g. a permissive research setting vs. a precautionary one).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from littleboy.core.enums import PolicyMode


class PolicyProfile(BaseModel):
    """Operational thresholds and toggles for one strictness posture."""

    model_config = ConfigDict(extra="forbid")

    mode: PolicyMode

    # Epistemic gates.
    min_data_quality_for_approval: float = Field(ge=0.0, le=1.0)
    min_evidence_quality_for_approval: float = Field(ge=0.0, le=1.0)
    min_confidence: float = Field(ge=0.0, le=1.0)
    data_quality_good: float = Field(
        ge=0.0, le=1.0, description="At/above this, the epistemic basis is treated as good."
    )

    # Coercion thresholds.
    max_coercion_for_acceptable: float = Field(
        ge=0.0, le=1.0, description="Above this, coercion is unacceptable unless justified."
    )
    coercion_moderate: float = Field(
        ge=0.0, le=1.0, description="Above this, coercion is non-trivial and needs scrutiny."
    )

    # Irreversibility.
    irreversible_requires_high_certainty: bool = True
    irreversible_min_epistemic: float = Field(
        ge=0.0, le=1.0, description="Min epistemic basis for an irreversible action."
    )

    # Consent / vulnerability / alternatives / manipulation.
    unknown_consent_is_blocker: bool = False
    vulnerability_confidence_penalty: float = Field(ge=0.0, le=1.0)
    alternative_downgrade_steps: int = Field(ge=0, le=3)
    informational_manipulation_severe: bool = True


# The four built-in profiles. STANDARD reproduces the v0.2 evaluator behaviour.
_PERMISSIVE = PolicyProfile(
    mode=PolicyMode.PERMISSIVE,
    min_data_quality_for_approval=0.25,
    min_evidence_quality_for_approval=0.20,
    min_confidence=0.20,
    data_quality_good=0.60,
    max_coercion_for_acceptable=0.75,
    coercion_moderate=0.40,
    irreversible_requires_high_certainty=False,
    irreversible_min_epistemic=0.40,
    unknown_consent_is_blocker=False,
    vulnerability_confidence_penalty=0.10,
    alternative_downgrade_steps=1,
    informational_manipulation_severe=False,
)

_STANDARD = PolicyProfile(
    mode=PolicyMode.STANDARD,
    min_data_quality_for_approval=0.35,
    min_evidence_quality_for_approval=0.30,
    min_confidence=0.30,
    data_quality_good=0.70,
    max_coercion_for_acceptable=0.60,
    coercion_moderate=0.30,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.50,
    unknown_consent_is_blocker=False,
    vulnerability_confidence_penalty=0.15,
    alternative_downgrade_steps=1,
    informational_manipulation_severe=True,
)

_STRICT = PolicyProfile(
    mode=PolicyMode.STRICT,
    min_data_quality_for_approval=0.50,
    min_evidence_quality_for_approval=0.45,
    min_confidence=0.45,
    data_quality_good=0.80,
    max_coercion_for_acceptable=0.45,
    coercion_moderate=0.20,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.65,
    unknown_consent_is_blocker=True,
    vulnerability_confidence_penalty=0.25,
    alternative_downgrade_steps=2,
    informational_manipulation_severe=True,
)

_PRECAUTIONARY = PolicyProfile(
    mode=PolicyMode.PRECAUTIONARY,
    min_data_quality_for_approval=0.60,
    min_evidence_quality_for_approval=0.55,
    min_confidence=0.55,
    data_quality_good=0.85,
    max_coercion_for_acceptable=0.35,
    coercion_moderate=0.15,
    irreversible_requires_high_certainty=True,
    irreversible_min_epistemic=0.75,
    unknown_consent_is_blocker=True,
    vulnerability_confidence_penalty=0.30,
    alternative_downgrade_steps=2,
    informational_manipulation_severe=True,
)

DEFAULT_PROFILES: dict[PolicyMode, PolicyProfile] = {
    PolicyMode.PERMISSIVE: _PERMISSIVE,
    PolicyMode.STANDARD: _STANDARD,
    PolicyMode.STRICT: _STRICT,
    PolicyMode.PRECAUTIONARY: _PRECAUTIONARY,
}

DEFAULT_POLICY_MODE = PolicyMode.STANDARD


def get_policy(policy: PolicyMode | PolicyProfile | str | None) -> PolicyProfile:
    """Resolve a policy mode (or an explicit profile, or ``None``) to a profile."""
    if policy is None:
        return DEFAULT_PROFILES[DEFAULT_POLICY_MODE]
    if isinstance(policy, PolicyProfile):
        return policy
    mode = PolicyMode(policy) if isinstance(policy, str) else policy
    return DEFAULT_PROFILES[mode]


# =============================================================================
# Named custom policies as data (v0.22)
# =============================================================================


class PolicyProvenance(BaseModel):
    """Where a custom policy came from -- so a tuned profile is never anonymous.

    Deliberately clock-free (no timestamps) so saved policies are deterministic
    and diffable. ``changes`` uses the tuner's ``'before -> after'`` rendering.
    """

    model_config = ConfigDict(extra="forbid")

    base: str = Field(description="The built-in policy the profile was derived from.")
    changes: dict[str, str] = Field(
        default_factory=dict, description="Changed parameters, as 'before -> after'."
    )
    description: str = ""


class NamedPolicy(BaseModel):
    """A custom :class:`PolicyProfile` with a name and provenance, storable as JSON.

    The built-in profiles stay untouched; a named policy is *data* -- saved,
    loaded, validated, and passed anywhere a policy mode is accepted. Reports
    produced under it carry the name (``policy_label``), so a verdict under a
    tuned policy is never mistaken for a built-in one.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    profile: PolicyProfile
    provenance: PolicyProvenance | None = None


def save_named_policy(path: str | Path, named: NamedPolicy) -> None:
    """Write a named policy to a JSON file (deterministic, human-diffable)."""
    Path(path).write_text(
        json.dumps(named.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def load_named_policy(path: str | Path) -> NamedPolicy:
    """Load and validate a named policy from a JSON file.

    Validation runs through the same models as everywhere else, so a corrupt or
    out-of-range profile is rejected on load, not discovered mid-evaluation.
    """
    return NamedPolicy.model_validate_json(Path(path).read_text(encoding="utf-8"))


def profile_changes(base: PolicyProfile, candidate: PolicyProfile) -> dict[str, str]:
    """Every differing parameter between two profiles, as ``'before -> after'``.

    The single canonical rendering: the tuner writes provenance with it, and
    :func:`verify_named_policy` recomputes with it, so a consistent provenance
    matches byte-for-byte.
    """
    return {
        name: f"{getattr(base, name)!r} -> {getattr(candidate, name)!r}"
        for name in PolicyProfile.model_fields
        if getattr(base, name) != getattr(candidate, name)
    }


class ProvenanceCheck(BaseModel):
    """The result of verifying a named policy's provenance against its profile."""

    model_config = ConfigDict(extra="forbid")

    name: str
    has_provenance: bool = True
    consistent: bool = True
    declared_changes: dict[str, str] = Field(default_factory=dict)
    recomputed_changes: dict[str, str] = Field(default_factory=dict)
    problems: list[str] = Field(default_factory=list)


def verify_named_policy(named: NamedPolicy) -> ProvenanceCheck:
    """Check that a policy's declared provenance matches what its profile actually is.

    The declared changes are recomputed from the named base profile and compared
    byte-for-byte. A mismatch means the file's *history* cannot be trusted (the
    profile itself is still valid and is what actually runs) -- reported honestly,
    never silently. A policy without provenance is consistent-by-vacuity but says
    so.
    """
    if named.provenance is None:
        return ProvenanceCheck(
            name=named.name,
            has_provenance=False,
            problems=["no provenance declared; nothing to verify"],
        )
    declared = dict(named.provenance.changes)
    try:
        base = DEFAULT_PROFILES[PolicyMode(named.provenance.base)]
    except ValueError:
        return ProvenanceCheck(
            name=named.name,
            consistent=False,
            declared_changes=declared,
            problems=[
                f"unknown base policy {named.provenance.base!r}: "
                "the provenance cannot be verified against any built-in"
            ],
        )
    recomputed = profile_changes(base, named.profile)
    problems: list[str] = []
    for key in sorted(recomputed.keys() - declared.keys()):
        problems.append(
            f"undeclared change: {key} is actually {recomputed[key]} "
            "but the provenance does not declare it"
        )
    for key in sorted(declared.keys() - recomputed.keys()):
        problems.append(f"declared change not present in the profile: {key} ({declared[key]})")
    for key in sorted(declared.keys() & recomputed.keys()):
        if declared[key] != recomputed[key]:
            problems.append(
                f"mismatched change for {key}: declared {declared[key]!r}, "
                f"actually {recomputed[key]!r}"
            )
    return ProvenanceCheck(
        name=named.name,
        consistent=not problems,
        declared_changes=declared,
        recomputed_changes=recomputed,
        problems=problems,
    )


def resolve_policy_ref(
    ref: str, *, registry: str | Path | None = None
) -> tuple[PolicyProfile | PolicyMode, str]:
    """Resolve a CLI-style policy reference to ``(policy, label)``.

    Resolution order: a built-in mode name (empty label); a **registered policy
    name** in the registry directory; a path to a named-policy JSON file (its
    name as the label). A reference that is both a registered name and an
    existing file is ambiguous and rejected loudly. Anything else raises
    ``ValueError``.
    """
    try:
        return PolicyMode(ref), ""
    except ValueError:
        pass
    registered = lookup_registered_policy(ref, directory=registry)
    path = Path(ref)
    if registered is not None and path.is_file():
        raise ValueError(
            f"ambiguous policy reference {ref!r}: it is both a registered policy name "
            f"and an existing file; use an explicit path (e.g. ./{ref}) or rename one"
        )
    if registered is not None:
        return registered.profile, registered.name
    if path.is_file():
        named = load_named_policy(path)
        return named.profile, named.name
    modes = ", ".join(m.value for m in PolicyMode)
    raise ValueError(
        f"unknown policy {ref!r}: not a built-in mode ({modes}), not a registered "
        "policy name, and not a policy file"
    )


# =============================================================================
# The policy registry (v0.24): a directory of named policies, listed & verified
# =============================================================================

REGISTRY_ENV_VAR = "LITTLEBOY_POLICY_DIR"
DEFAULT_REGISTRY_DIR = Path("policies")


def registry_dir(override: str | Path | None = None) -> Path:
    """The registry directory: explicit override, else $LITTLEBOY_POLICY_DIR, else ./policies."""
    if override is not None:
        return Path(override)
    env = os.environ.get(REGISTRY_ENV_VAR)
    if env:
        return Path(env)
    return DEFAULT_REGISTRY_DIR


class RegistryEntry(BaseModel):
    """One file in the policy registry, with its load and provenance status."""

    model_config = ConfigDict(extra="forbid")

    file: str
    name: str = ""
    base: str = ""
    changes: dict[str, str] = Field(default_factory=dict)
    description: str = ""
    loadable: bool = True
    has_provenance: bool = False
    consistent: bool = True
    flagged: bool = Field(
        default=False,
        description=(
            "True when the entry cannot be trusted as-is: unreadable, tampered "
            "provenance, a duplicated name, or a name colliding with a built-in. "
            "Missing provenance alone does not flag."
        ),
    )
    problems: list[str] = Field(default_factory=list)


class PolicyRegistry(BaseModel):
    """A scan of the registry directory: every policy, verified, nothing trusted blindly."""

    model_config = ConfigDict(extra="forbid")

    directory: str
    exists: bool = True
    entries: list[RegistryEntry] = Field(default_factory=list)
    n_policies: int = 0
    n_flagged: int = 0
    duplicate_names: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _registry_files(directory: Path) -> list[Path]:
    # the tuner's --save writes <stem>.impact.json companions; they are reports, not policies
    return sorted(
        path for path in directory.glob("*.json") if not path.name.endswith(".impact.json")
    )


def scan_policy_registry(directory: str | Path | None = None) -> PolicyRegistry:
    """Scan the registry: load and provenance-verify every policy file, flag what's wrong.

    Deterministic (files sorted by name). Flagged = unreadable, tampered
    provenance, duplicate names, or a name colliding with a built-in mode --
    the entries that must not be used as-is. A policy without provenance is
    listed but not flagged (less history is not an integrity failure).
    """
    d = registry_dir(directory)
    if not d.is_dir():
        return PolicyRegistry(
            directory=str(d),
            exists=False,
            notes=[f"no registry directory at {d}; create it or set ${REGISTRY_ENV_VAR}"],
        )

    entries: list[RegistryEntry] = []
    builtin_names = {m.value for m in PolicyMode}
    for path in _registry_files(d):
        try:
            named = load_named_policy(path)
        except Exception as exc:  # noqa: BLE001 - unreadable files must be listed, not crash
            entries.append(
                RegistryEntry(
                    file=path.name,
                    loadable=False,
                    consistent=False,
                    flagged=True,
                    problems=[f"not a valid named policy: {type(exc).__name__}"],
                )
            )
            continue
        check = verify_named_policy(named)
        problems = list(check.problems)
        flagged = check.has_provenance and not check.consistent
        if named.name in builtin_names:
            problems.append(
                f"name {named.name!r} collides with a built-in policy; "
                "it can never be resolved by name"
            )
            flagged = True
        entries.append(
            RegistryEntry(
                file=path.name,
                name=named.name,
                base=named.provenance.base if named.provenance else "",
                changes=dict(named.provenance.changes) if named.provenance else {},
                description=named.provenance.description if named.provenance else "",
                loadable=True,
                has_provenance=check.has_provenance,
                consistent=check.consistent,
                flagged=flagged,
                problems=problems,
            )
        )

    name_counts: dict[str, int] = {}
    for entry in entries:
        if entry.loadable:
            name_counts[entry.name] = name_counts.get(entry.name, 0) + 1
    duplicates = sorted(name for name, count in name_counts.items() if count > 1)
    for entry in entries:
        if entry.name in duplicates:
            entry.flagged = True
            entry.problems.append(
                f"name {entry.name!r} is used by more than one registry file; "
                "by-name resolution is ambiguous"
            )

    notes = [
        "flagged = unreadable, tampered provenance, duplicate name, or built-in collision",
        "a policy without provenance is listed but not flagged (less history, not tampering)",
    ]
    return PolicyRegistry(
        directory=str(d),
        entries=entries,
        n_policies=len(entries),
        n_flagged=sum(1 for entry in entries if entry.flagged),
        duplicate_names=duplicates,
        notes=notes,
    )


def lookup_registered_policy(
    name: str, *, directory: str | Path | None = None
) -> NamedPolicy | None:
    """Find a policy by its *name* in the registry; ``None`` if absent.

    Raises ``ValueError`` when more than one registry file carries the name --
    by-name resolution must never silently pick one of several.
    """
    d = registry_dir(directory)
    if not d.is_dir():
        return None
    matches: list[tuple[Path, NamedPolicy]] = []
    for path in _registry_files(d):
        try:
            named = load_named_policy(path)
        except Exception:  # noqa: BLE001 - unreadable files cannot match a name
            continue
        if named.name == name:
            matches.append((path, named))
    if not matches:
        return None
    if len(matches) > 1:
        files = ", ".join(path.name for path, _ in matches)
        raise ValueError(f"registered policy name {name!r} is ambiguous: defined by {files} in {d}")
    return matches[0][1]
