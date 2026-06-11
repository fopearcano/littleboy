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
import hmac
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
TRUSTED_KEYS_NAME = "trusted_keys.json"
TRUSTED_KEYS_ENV_VAR = "LITTLEBOY_TRUSTED_KEYS"
_GENESIS = "0" * 64  # the previous-hash of the very first entry
# fields that are NOT part of the chain content (the chain pointer and the
# signature metadata): excluding them keeps the v0.25 chain hashes unchanged,
# so signing an entry never perturbs the integrity chain.
_NON_CONTENT = ("prev_hash", "key_id", "signature")


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
    key_id: str = Field(default="", description="The signing key id, if this entry was signed.")
    signature: str = Field(
        default="", description="Detached HMAC-SHA256 over the entry, if signed (hex)."
    )


def _entry_payload(entry: DecisionEntry) -> dict:
    """The chained content of an entry: everything except the chain pointer and signature."""
    data = entry.model_dump(mode="json")
    for field in _NON_CONTENT:
        data.pop(field, None)
    return data


def entry_hash(entry: DecisionEntry) -> str:
    """The hash an entry contributes to the chain (its content, excluding chain/signature)."""
    canonical = json.dumps(_entry_payload(entry), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# =============================================================================
# Optional detached signatures (v0.26): authority on top of integrity
# =============================================================================
#
# The hash chain proves *what* was adopted (integrity); a signature proves *who*
# adopted it (authority). HMAC-SHA256 over the entry's canonical bytes, with a
# shared secret keyed by id. Signing is strictly opt-in: an unsigned log behaves
# exactly as in v0.25. NB: HMAC is symmetric -- the verifier holds the same
# secret as the signer, so this authenticates within a trust boundary (a team
# sharing a secret), not against the holder of the secret. True non-repudiation
# needs asymmetric signatures, which are out of scope (stdlib only).


class SigningKey(BaseModel):
    """A signer's private material: a key id and a hex secret. Never in the registry."""

    model_config = ConfigDict(extra="forbid")

    key_id: str
    secret: str = Field(description="Hex-encoded shared secret for HMAC-SHA256.")


class TrustedKey(BaseModel):
    """One trusted key the verifier holds: its id and the shared secret to check with."""

    model_config = ConfigDict(extra="forbid")

    key_id: str
    secret: str


def load_signing_key(path: str | Path) -> SigningKey:
    """Load a signing key from a JSON file (``{"key_id": ..., "secret": <hex>}``)."""
    return SigningKey.model_validate_json(Path(path).read_text(encoding="utf-8"))


def trusted_keys_path(directory: str | Path | None = None) -> Path:
    """Where the verifier's trusted-keys file lives (env override, else in the registry)."""
    import os

    env = os.environ.get(TRUSTED_KEYS_ENV_VAR)
    if env:
        return Path(env)
    return registry_dir(directory) / TRUSTED_KEYS_NAME


def load_trusted_keys(path: str | Path) -> dict[str, str]:
    """Load ``key_id -> secret`` from a trusted-keys JSON file (list of ``TrustedKey``)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    keys = [TrustedKey.model_validate(item) for item in raw]
    return {k.key_id: k.secret for k in keys}


def _signable_bytes(entry: DecisionEntry) -> bytes:
    """The exact bytes a signature covers: the whole entry except the signature itself.

    Includes ``key_id`` and ``prev_hash`` -- so the signature binds the signer's
    identity and the entry's chain position, not just its content.
    """
    data = entry.model_dump(mode="json")
    data.pop("signature", None)
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_entry(entry: DecisionEntry, key: SigningKey) -> str:
    """The detached HMAC-SHA256 (hex) for ``entry`` under ``key`` (entry must carry key.key_id)."""
    return hmac.new(bytes.fromhex(key.secret), _signable_bytes(entry), hashlib.sha256).hexdigest()


def entry_signature_status(entry: DecisionEntry, trusted: dict[str, str]) -> str:
    """Classify an entry's signature: unsigned / signed-trusted / -untrusted / -invalid.

    ``signed-untrusted`` means the key id is not in ``trusted`` (cannot verify);
    ``signed-invalid`` means the key is trusted but the HMAC does not match
    (tampering, or the wrong secret) -- always a problem.
    """
    if not entry.signature:
        return "unsigned"
    secret = trusted.get(entry.key_id)
    if secret is None:
        return "signed-untrusted"
    expected = hmac.new(bytes.fromhex(secret), _signable_bytes(entry), hashlib.sha256).hexdigest()
    return "signed-trusted" if hmac.compare_digest(expected, entry.signature) else "signed-invalid"


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
    signing_key: SigningKey | None = None,
) -> DecisionEntry:
    """Append one adoption to the log, refusing a flagged policy unless ``force``.

    Returns the appended :class:`DecisionEntry`. A flagged policy (tampered
    provenance) raises ``ValueError`` unless ``force=True``, in which case the
    entry records ``forced=True`` and the flags present at adoption -- the
    override is logged, never silent. When ``signing_key`` is given, the entry is
    HMAC-signed; signing never changes the integrity chain (the signature is not
    chain content), so signed and unsigned logs chain identically.
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
        key_id=signing_key.key_id if signing_key else "",
    )
    if signing_key is not None:
        entry = entry.model_copy(update={"signature": sign_entry(entry, signing_key)})
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
    signature_status: list[str] = Field(
        default_factory=list, description="Per-entry signature classification, in order."
    )
    trusted_keys_found: bool = False
    require_signatures: bool = False
    notes: list[str] = Field(default_factory=list)


def verify_decision_log(
    directory: str | Path | None = None,
    *,
    trusted_keys: str | Path | None = None,
    require_signatures: bool = False,
) -> DecisionLogReport:
    """Verify the chain, the registry content, and (optionally) the entry signatures.

    Three checks: the **hash chain** (each entry's ``prev_hash`` must equal the
    prior entry's content hash, sequence numbers contiguous); **content drift**
    (the adopted ``profile_hash`` must still match the registry file carrying that
    name -- a silent post-adoption swap); and **signatures** against a trusted-keys
    file (default: ``trusted_keys.json`` in the registry, or ``$LITTLEBOY_TRUSTED_KEYS``).
    A ``signed-invalid`` entry is always a problem; ``unsigned`` / ``signed-untrusted``
    become problems only under ``require_signatures``.
    """
    d = registry_dir(directory)
    path = decision_log_path(directory)
    if not path.is_file():
        return DecisionLogReport(
            directory=str(d),
            exists=False,
            require_signatures=require_signatures,
            notes=[f"no decision log at {path}; adopt a policy to start one"],
        )

    entries = read_decision_log(directory)
    problems: list[str] = []

    keys_path = Path(trusted_keys) if trusted_keys is not None else trusted_keys_path(directory)
    trusted: dict[str, str] = {}
    trusted_found = keys_path.is_file()
    if trusted_found:
        try:
            trusted = load_trusted_keys(keys_path)
        except Exception as exc:  # noqa: BLE001 - a broken keyfile is reported, not raised
            problems.append(f"trusted-keys file {keys_path} is unreadable: {type(exc).__name__}")
            trusted_found = False

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

    # 3. signatures (opt-in): invalid is always a problem; missing/untrusted only when required
    signature_status = [entry_signature_status(entry, trusted) for entry in entries]
    for i, (entry, status) in enumerate(zip(entries, signature_status, strict=True)):
        if status == "signed-invalid":
            problems.append(
                f"entry {i} ('{entry.policy_name}'): signature is INVALID for key "
                f"'{entry.key_id}' -- the entry was altered or signed with the wrong secret"
            )
        elif require_signatures and status != "signed-trusted":
            detail = (
                "is unsigned"
                if status == "unsigned"
                else f"is signed by untrusted key '{entry.key_id}'"
            )
            problems.append(
                f"entry {i} ('{entry.policy_name}'): {detail}, but signatures are required"
            )

    notes = [
        "the hash chain catches altered/removed/reordered entries; the content check catches "
        "a registry file swapped after adoption",
        "clock-free: the log carries no timestamps, so it stays deterministic and diffable",
    ]
    if not trusted_found:
        notes.append(
            f"no trusted-keys file at {keys_path}; signed entries read as 'signed-untrusted'"
        )
    notes.append(
        "signatures are HMAC (symmetric): the verifier holds the same secret as the signer, so "
        "they authenticate within a trust boundary, not against the secret-holder"
    )
    return DecisionLogReport(
        directory=str(d),
        n_entries=len(entries),
        entries=entries,
        current=current,
        chain_intact=chain_intact,
        n_problems=len(problems),
        problems=problems,
        signature_status=signature_status,
        trusted_keys_found=trusted_found,
        require_signatures=require_signatures,
        notes=notes,
    )
