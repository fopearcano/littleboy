# LittleBoy policy profiles (v0.3)

A **policy profile** (`littleboy.rules.policy.PolicyProfile`) is a bundle of
*operational parameters* — thresholds and toggles — that control how strict the
rule engine is. A policy changes how the axioms are **applied** to uncertain,
real-world data; it never changes the axioms themselves.

> These numbers are deliberate, documented defaults, **not** claims of absolute
> moral truth. They let the same case be examined under different risk postures.

## The four modes

| Mode | Posture |
|------|---------|
| `permissive` | Tolerant: higher coercion tolerated, lower data bars, unknowns rarely block. For low-stakes or exploratory use. |
| `standard` *(default)* | Balanced. Reproduces the v0.2 evaluator behaviour. |
| `strict` | Cautious: lower coercion ceiling, higher data/evidence/confidence bars, unknown consent blocks. |
| `precautionary` | Most cautious: the strictest thresholds; treats uncertainty as strongly disfavouring approval. |

## What a policy controls

| Parameter | Meaning |
|-----------|---------|
| `min_data_quality_for_approval` | Epistemic basis below this → `INSUFFICIENT_DATA`. |
| `min_evidence_quality_for_approval` | Evidence below this is flagged and lowers confidence. |
| `min_confidence` | Final confidence below this → `INSUFFICIENT_DATA`. |
| `data_quality_good` | At/above this the epistemic basis counts as "good" (needed for `ACCEPTABLE`). |
| `max_coercion_for_acceptable` | Above this, coercion is unacceptable unless justified (the "high" threshold). |
| `coercion_moderate` | Above this, coercion is non-trivial and triggers scrutiny of alternatives/justification. |
| `irreversible_requires_high_certainty` | Whether an irreversible act demands a strong epistemic basis. |
| `irreversible_min_epistemic` | The epistemic bar for an irreversible act. |
| `unknown_consent_is_blocker` | Whether unknown consent blocks confident approval (vs. only lowering confidence). |
| `vulnerability_confidence_penalty` | How strongly high vulnerability lowers confidence. |
| `alternative_downgrade_steps` | How many notches a feasible less-coercive alternative downgrades the verdict. |
| `informational_manipulation_severe` | Whether informational manipulation is treated as severe coercion. |

## Default values

| Parameter | permissive | standard | strict | precautionary |
|-----------|:---:|:---:|:---:|:---:|
| min_data_quality_for_approval | 0.25 | 0.35 | 0.50 | 0.60 |
| min_evidence_quality_for_approval | 0.20 | 0.30 | 0.45 | 0.55 |
| min_confidence | 0.20 | 0.30 | 0.45 | 0.55 |
| data_quality_good | 0.60 | 0.70 | 0.80 | 0.85 |
| max_coercion_for_acceptable | 0.75 | 0.60 | 0.45 | 0.35 |
| coercion_moderate | 0.40 | 0.30 | 0.20 | 0.15 |
| irreversible_requires_high_certainty | false | true | true | true |
| irreversible_min_epistemic | 0.40 | 0.50 | 0.65 | 0.75 |
| unknown_consent_is_blocker | false | false | true | true |
| vulnerability_confidence_penalty | 0.10 | 0.15 | 0.25 | 0.30 |
| alternative_downgrade_steps | 1 | 1 | 2 | 2 |
| informational_manipulation_severe | false | true | true | true |

## How profiles change strictness — worked examples

- `examples/policy_permissive_case.json` (firm but reversible mandate, coercion
  ≈ 0.65): **`NOT_ACCEPTABLE` under `standard`** (above its 0.60 ceiling, no
  justification) but **`ACCEPTABLE_WITH_RESERVATIONS` under `permissive`** (below
  its 0.75 ceiling).
- `examples/policy_strict_case.json` (mild coercion, **unknown consent**):
  **`ACCEPTABLE_WITH_RESERVATIONS` under `standard`** (unknown consent only lowers
  confidence) but **`ETHICALLY_SUSPICIOUS` under `strict`** (unknown consent is a
  blocker).

## Choosing a policy

```bash
littleboy evaluate examples/policy_strict_case.json --policy strict
littleboy evaluate examples/policy_strict_case.json --policy strict --format text
```

```python
from littleboy import EthicalEvaluator, PolicyMode
report = EthicalEvaluator(PolicyMode.STRICT).evaluate(case)
```

You can also pass a fully custom `PolicyProfile` to `EthicalEvaluator(...)` if you
need parameters between the built-in modes. The chosen mode is recorded on every
report (`policy_mode`) and in the reasoning trace, so a verdict is never
separable from the policy that produced it.

## Named custom policies as data (v0.22)

A vetted candidate (typically from the dry-run tuner) can become a **first-class,
named profile without touching the built-ins** — adoption as data:

- **`NamedPolicy`** bundles a `PolicyProfile` with a `name` and a
  `PolicyProvenance` (the base it was derived from, the exact parameter changes
  as `'before -> after'`, and a free-text description). Provenance is
  deliberately **clock-free** — no timestamps — so saved policies are
  deterministic and diffable.
- **Save / load / validate**: `save_named_policy` writes human-diffable JSON;
  `load_named_policy` re-validates everything through the same models as
  everywhere else, so a corrupt or out-of-range profile is rejected *on load*,
  not discovered mid-evaluation. `littleboy tune ... --save my_policy.json
  --name research_gate_025 --describe "..."` writes the policy **plus the full
  tuning-impact report alongside** (`my_policy.impact.json`) — the decision
  record archived next to the decision.
- **Use anywhere a mode name is accepted**: every CLI `--policy` (and `tune
  --base`) resolves either a built-in mode name or a path to a named-policy
  file (`littleboy evaluate case.json --policy my_policy.json`); in the
  library, `resolve_policy_ref` does the same, and every engine already takes a
  `PolicyProfile`.
- **Never mistaken for a built-in**: every `EvaluationReport` carries a
  `policy_label` — empty for built-ins, the custom name otherwise — and the
  text rendering says it outright:
  `VERDICT: ... [policy: research_gate_025 (custom, base standard)]`. CLI
  commands that take a custom file announce it on stderr (stdout stays pure
  JSON), and round-trip behaviour (save → load → identical verdicts) plus the
  saved payload are pinned by tests and a golden file.

The built-in profiles remain untouched and untouchable by all of this: a named
policy is a file you chose to write, carrying its own history.

## Calibration under a named policy (v0.23)

An adopted profile is a **first-class measurement subject**, and its history is
**verified, never silently trusted**:

- **Reliability rows under its own name**: `run_reliability(...,
  extra_policies=[named])` and `recommend_policy_for_stakeholder(...,
  extra_policies=...)` enter named policies into the per-policy tables and the
  recommendation ranking *alongside* the four built-ins — the name in the
  `policy` column, never conflated with its base, and a name that collides with
  a built-in is rejected. CLI: `littleboy calibrate --scope reliability
  --with-policy my_policy.json` and `littleboy recommend-policy --with-policy
  my_policy.json` (repeatable). A consistency test pins the named row's counts
  to the tuner's after-numbers: the same measurement, two views.
- **The name everywhere it appears**: `diagnose` and `explain-disagreement`
  under a custom policy now carry the name in the report itself
  (`DIAGNOSIS: engine[research_gate_025] vs consensus`,
  `engine[research_gate_025]` in explanations), and `explain-disagreement
  --against` accepts a named-policy file too, so a custom profile can be
  diffed against a built-in (or another custom) case by case.
- **Provenance integrity** (`verify_named_policy`): the declared changes are
  *recomputed* from the named base profile via the single canonical rendering
  (`profile_changes`, shared with the tuner) and compared byte-for-byte. Every
  kind of tampering is named specifically — a mismatched value, an undeclared
  change, a declared-but-absent change, an unknown base — and the CLI warns
  loudly on stderr whenever a tampered file is loaded: *the profile is what
  runs; the declared history cannot be trusted.* A policy without provenance is
  consistent-by-vacuity and says so. The check never blocks (the profile itself
  is validated separately); it makes the lie visible.

## The policy registry (v0.24)

A project's named policies live in **one place** — a registry directory
(`./policies` by default, `$LITTLEBOY_POLICY_DIR` or `--registry` to override) —
listed, verified, and referenced **by name**:

- **`littleboy policies`** scans the directory (deterministically, sorted by
  filename; the tuner's `*.impact.json` companions are excluded) and lists every
  policy with its status: `ok`, `no-prov` (less history, not flagged),
  `FLAGGED` (tampered provenance, a duplicated name, or a name colliding with a
  built-in), or `UNREADABLE`. Every problem is printed under its entry — a
  drifted file is visible **before it is ever used**.
- **`littleboy policies --verify`** exits non-zero when anything is flagged —
  a one-line CI gate for the whole registry. Missing provenance does not fail
  the gate; tampering, duplicates, collisions, and unreadable files do.
- **Resolution by name, ambiguities rejected loudly**: every `--policy`,
  `--with-policy`, `tune --base`, and `explain-disagreement --against` resolves
  in a fixed order — **built-in mode → registered name → file path**. A built-in
  name always wins (a registry entry shadowing one is flagged, never silently
  used); a reference that is both a registered name and an existing file is an
  error telling you to disambiguate; a registered policy named like a labeller
  is rejected for `--against`; duplicate names inside the registry refuse
  by-name resolution entirely. Tampered policies warn on use exactly as files
  do.

The registry is still just files: nothing is installed, nothing global mutates,
and `scan_policy_registry` / `lookup_registered_policy` give the library the
same capabilities as the CLI.

## The decision log (v0.25)

The registry holds the policies; the **decision log** (`decisions.jsonl` in the
registry directory) holds the **history of choosing between them** — an
append-only, clock-free, hash-chained record:

- **`littleboy adopt <name|file> --because "..."`** appends one entry: a
  sequence number, the policy name and a **content hash** of its profile, the
  base it derived from, the policy it replaced, the stated reason, and a small
  digest of the tuner's impact report (attached automatically from
  `<file>.impact.json` when adopting a saved policy). It **refuses to adopt a
  flagged policy** (tampered provenance) unless `--force`, and a forced adoption
  records `forced` and the flags present — the override is logged, never silent.
- **clock-free**: no timestamps, so the log is deterministic and diffable, and a
  replayed adoption produces byte-identical bytes (a regression-friendly
  property, tested directly).
- **`littleboy decisions [--verify]`** lists the history and runs two integrity
  checks: the **hash chain** (each entry pins the previous entry's content hash,
  so an altered, removed, or reordered entry breaks the chain) and **content
  drift** (each entry pins the adopted profile's hash, so a registry file
  *silently swapped after adoption* is caught — the file no longer matches what
  was adopted). `--verify` exits non-zero on any problem, a CI gate for the log.
- **`littleboy policies`** now shows the currently adopted policy (`adopted:
  <name>`, marked `*` in the listing) — the project's working policy, read from
  the tail of the log.

The log proves *integrity*, not *authority*: it shows that the recorded history
matches the current files (or exactly where it does not), but it cannot vouch for
who made a change or why. It makes a silent swap impossible to hide, not
impossible to attempt.

## Signed adoptions (v0.26)

The log proves integrity by default; **signing** adds *authority* — who adopted,
not just what — strictly opt-in, stdlib-only, and clock-free:

- **`littleboy adopt <policy> --because "..." --sign-with KEYFILE`** attaches a
  detached **HMAC-SHA256** over the entry's canonical bytes (the keyfile is
  `{"key_id": ..., "secret": "<hex>"}`, the signer's private material — never in
  the registry). The signature covers the entry's content, its `key_id`, and its
  chain position, but **not the chain itself**: signing never perturbs the
  integrity chain, so signed and unsigned logs chain identically and an unsigned
  log behaves exactly as in v0.25. HMAC is deterministic, so a signed log stays
  byte-reproducible.
- **`littleboy decisions --verify`** classifies each entry against a
  **trusted-keys file** (`trusted_keys.json` in the registry, or
  `$LITTLEBOY_TRUSTED_KEYS` / `--trusted-keys`): `unsigned`, `signed-trusted`,
  `signed-untrusted` (unknown key id — cannot verify), or `signed-invalid` (key
  trusted but the HMAC does not match — tampering or the wrong secret). A
  `signed-invalid` entry is **always** a problem; `--require-signatures` makes
  `unsigned` and `signed-untrusted` failures too, a stricter CI gate. Tampering
  with a signed entry's content flips it to `signed-invalid` (the HMAC no longer
  matches), so signatures catch edits the chain check alone would only catch at
  the chained boundary.

**The honest limit, stated plainly**: HMAC is *symmetric* — the verifier holds
the same secret as the signer, so a signature authenticates *within a trust
boundary* (a team that shares a secret), not *against* the secret-holder. Anyone
with the trusted-keys file can forge a valid signature. True non-repudiation
needs asymmetric signatures, which are deliberately out of scope (stdlib only, no
third-party crypto). Keeping the trusted-keys file out of the shared registry
(via `$LITTLEBOY_TRUSTED_KEYS`) is the meaningful mitigation.
