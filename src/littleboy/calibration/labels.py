"""Import real, independent human labels from a CSV and overlay them onto cases.

The synthetic persona panel (``generator.py``) is a stand-in. The honest article
is labels from *actual* independent people: send them the cases, collect a CSV of
``case_id,labeler,verdict`` rows, and overlay those labels onto the known cases by
id. The resulting :class:`OutcomeCorpus` runs through the *existing*
``run_reliability`` / ``recommend_policy`` / ``fit_threshold_policy`` unchanged --
the engine never learns who labelled what; it is only measured against them.

Everything here is deterministic and stdlib-only (``csv``); no network, no service.
"""

from __future__ import annotations

import csv
import io
from collections import Counter
from pathlib import Path

from littleboy.calibration.models import (
    LabelerVerdict,
    OutcomeCorpus,
    OutcomeEntry,
)
from littleboy.core.enums import Verdict

# Tie-break order for a split panel: when no single verdict has a majority, defer
# to the *more cautious* reading (lower = more cautious). Independent judges who
# split evenly should not have their consensus over-claim permissibility.
_CAUTION_ORDER = {
    Verdict.NOT_ACCEPTABLE: 0,
    Verdict.ETHICALLY_SUSPICIOUS: 1,
    Verdict.INSUFFICIENT_DATA: 2,
    Verdict.ACCEPTABLE_WITH_RESERVATIONS: 3,
    Verdict.ACCEPTABLE: 4,
}

_VERDICT_ALIASES = {
    "acceptable": Verdict.ACCEPTABLE,
    "acceptable_with_reservations": Verdict.ACCEPTABLE_WITH_RESERVATIONS,
    "reservations": Verdict.ACCEPTABLE_WITH_RESERVATIONS,
    "ethically_suspicious": Verdict.ETHICALLY_SUSPICIOUS,
    "suspicious": Verdict.ETHICALLY_SUSPICIOUS,
    "not_acceptable": Verdict.NOT_ACCEPTABLE,
    "unacceptable": Verdict.NOT_ACCEPTABLE,
    "insufficient_data": Verdict.INSUFFICIENT_DATA,
    "insufficient": Verdict.INSUFFICIENT_DATA,
}


def parse_verdict(raw: str) -> Verdict:
    """Parse a verdict from a human-written cell, forgiving case/spacing/hyphens."""
    key = raw.strip().lower().replace("-", "_").replace(" ", "_")
    if key in _VERDICT_ALIASES:
        return _VERDICT_ALIASES[key]
    try:
        return Verdict(key)
    except ValueError as exc:
        allowed = ", ".join(sorted({v.value for v in Verdict}))
        raise ValueError(f"unknown verdict {raw!r}; expected one of: {allowed}") from exc


def consensus_verdict(labels: list[LabelerVerdict]) -> Verdict:
    """Majority verdict over a panel; ties broken toward the more cautious reading."""
    if not labels:
        raise ValueError("cannot take a consensus of zero labels")
    counts = Counter(lv.verdict for lv in labels)
    top = max(counts.values())
    tied = [v for v, c in counts.items() if c == top]
    if len(tied) == 1:
        return tied[0]
    return min(tied, key=lambda v: _CAUTION_ORDER[v])


def parse_labels_csv(
    text: str,
) -> tuple[dict[str, list[LabelerVerdict]], dict[str, str]]:
    """Parse ``case_id,labeler,verdict[,split]`` rows into per-case labels and splits.

    Returns ``(labels_by_case, split_by_case)``. The header is required and may be
    in any column order; an optional ``split`` column overrides the base corpus's
    split for that case. Rows are de-duplicated per (case, labeler) -- the last
    wins -- so re-sending a corrected label is safe.
    """
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("empty CSV: a header row (case_id,labeler,verdict) is required")
    fields = {name.strip().lower() for name in reader.fieldnames}
    required = {"case_id", "labeler", "verdict"}
    missing = required - fields
    if missing:
        raise ValueError(f"CSV missing required column(s): {', '.join(sorted(missing))}")

    # last label per (case, labeler) wins; preserve first-seen order of labelers
    by_case: dict[str, dict[str, Verdict]] = {}
    split_by_case: dict[str, str] = {}
    for row in reader:
        norm = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        case_id = norm.get("case_id", "")
        labeler = norm.get("labeler", "")
        verdict_cell = norm.get("verdict", "")
        if not case_id or not labeler or not verdict_cell:
            continue  # skip blank / partial rows
        by_case.setdefault(case_id, {})[labeler] = parse_verdict(verdict_cell)
        split = norm.get("split", "")
        if split:
            split_by_case[case_id] = split

    labels_by_case = {
        case_id: [LabelerVerdict(labeler=name, verdict=v) for name, v in labelers.items()]
        for case_id, labelers in by_case.items()
    }
    return labels_by_case, split_by_case


def apply_labels(
    base: OutcomeCorpus,
    labels_by_case: dict[str, list[LabelerVerdict]],
    split_by_case: dict[str, str] | None = None,
    *,
    title: str | None = None,
    drop_unlabelled: bool = True,
) -> OutcomeCorpus:
    """Overlay externally-supplied labels onto the cases of a base corpus, by id.

    The cases (and their splits, unless overridden) come from ``base``; the labels,
    the consensus, and the inter-labeller agreement come from the supplied data.
    Unlabelled base cases are dropped (they cannot contribute to reliability) unless
    ``drop_unlabelled=False``.
    """
    split_by_case = split_by_case or {}
    entries: list[OutcomeEntry] = []
    for entry in base.entries:
        labels = labels_by_case.get(entry.id)
        if labels is None:
            if not drop_unlabelled:
                entries.append(entry)
            continue
        entries.append(
            OutcomeEntry(
                id=entry.id,
                description=entry.description,
                case=entry.case,
                split=split_by_case.get(entry.id, entry.split),
                human_verdict=consensus_verdict(labels),
                labeler="panel",
                labels=labels,
            )
        )
    if not entries:
        raise ValueError(
            "no base case ids matched the supplied labels; "
            "check that the CSV's case_id column matches the corpus"
        )
    return OutcomeCorpus(
        title=title or f"{base.title} (relabelled from external labels)",
        description=(
            "Cases from a base corpus, relabelled with independently-supplied human "
            "verdicts. Reliability and recommendation run against these unchanged."
        ),
        entries=entries,
    )


def outcome_corpus_from_csv(
    base: OutcomeCorpus,
    source: str | Path,
    *,
    title: str | None = None,
    drop_unlabelled: bool = True,
) -> OutcomeCorpus:
    """Build a relabelled corpus from a base corpus of cases and a labels CSV file."""
    text = Path(source).read_text(encoding="utf-8")
    labels_by_case, split_by_case = parse_labels_csv(text)
    return apply_labels(
        base,
        labels_by_case,
        split_by_case,
        title=title,
        drop_unlabelled=drop_unlabelled,
    )


def labels_to_csv(corpus: OutcomeCorpus) -> str:
    """Emit a corpus's per-labeler verdicts as a CSV (a template / round-trip export)."""
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["case_id", "labeler", "verdict", "split"])
    for entry in corpus.entries:
        for lv in entry.labels:
            writer.writerow([entry.id, lv.labeler, lv.verdict.value, entry.split])
    return out.getvalue()
