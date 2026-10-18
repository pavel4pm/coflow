"""Plain-text rendering for the CLI: the share line first, the integrity line first when not
``ok``, every reason in words with its date and the date's source; ``dec waiting --brief`` (at
most 8 items, one line each) (spec §5.6).

Owned by track X (interfaces); increment I1, spec §12.2.

Every function renders a view of ``interfaces/views/card.py`` (or a kernel report) and nothing
else, so the text says exactly what MCP returns. Every answer ends with its footer: the instance
role, the as-of instant in the owner's zone, the coverage notes and the authority. The output is
deterministic: the same view gives the same text.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime
from pathlib import Path
from typing import cast

from coflow.kernel.context import parse_instant, zone
from coflow.kernel.ops.doctor import DoctorReport
from coflow.kernel.ops.instance import InstanceInfo

__all__ = [
    "BRIEF_MAX",
    "MORNING_PULL_RECIPE",
    "render_card",
    "render_doctor",
    "render_error",
    "render_import",
    "render_init",
    "render_integrity",
    "render_list",
    "render_recipe",
    "render_shadow",
    "render_token",
    "render_view",
    "render_waiting",
]

BRIEF_MAX = 8
"""``dec waiting --brief`` prints at most this many items (§5.6)."""

_TITLE_BRIEF = 40


def _d(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _l(value: object) -> list[object]:
    return cast(list[object], value) if isinstance(value, list) else []


def _s(value: object, default: str = "-") -> str:
    return default if value is None or value == "" else str(value)


def _cut(text: str, width: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 3].rstrip() + "..."


def _share(value: object) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(str(value)) * 100:.0f} %"
    except ValueError:
        return str(value)


def _local(instant: object, tz: object) -> str:
    if not isinstance(instant, str):
        return "-"
    moment = parse_instant(instant)
    if isinstance(tz, str) and tz:
        local: datetime = moment.astimezone(zone(tz))
        return f"{local:%Y-%m-%d %H:%M} ({tz})"
    return instant


def _footer(view: Mapping[str, object]) -> list[str]:
    lines = [
        f"-- instance: {_s(view.get('instance_role'), 'unknown')} | as of "
        f"{_local(view.get('as_of'), view.get('timezone'))} | axis {_s(view.get('axis'))}"
    ]
    if view.get("stale"):
        lines.append("-- stale: the data behind this answer is older than its freshness limit")
    lines.extend(f"-- coverage: {note}" for note in _l(view.get("coverage")))
    if view.get("authority"):
        lines.append(f"-- authority: {view['authority']}")
    return lines


def _authority_note(item: Mapping[str, object]) -> str:
    authority = _d(item.get("authority"))
    if authority.get("writable_here") is False:
        return f"  [{authority.get('text')}]"
    return ""


# ==================================================================================================
# Errors


def render_error(payload: Mapping[str, object]) -> str:
    """A typed error (§5.1): the code, what it means, what would make the call valid."""
    error = _d(payload.get("error"))
    kind = _s(error.get("type"), "error")
    code = error.get("code")
    head = f"{kind} {code}" if code else kind
    lines = [f"{head}: {_s(error.get('detail'), '')}".rstrip(": ")]
    if _l(error.get("missing")):
        lines.append("  missing: " + ", ".join(str(m) for m in _l(error.get("missing"))))
    if _l(error.get("allowed")):
        lines.append("  allowed: " + ", ".join(str(a) for a in _l(error.get("allowed"))))
    if _l(error.get("candidates")):
        lines.append("  did you mean: " + ", ".join(str(c) for c in _l(error.get("candidates"))))
    if payload.get("instance_role"):
        lines.append(f"-- instance: {payload['instance_role']}")
    return "\n".join(lines)


# ==================================================================================================
# The waiting list


def _first_action(item: Mapping[str, object]) -> str | None:
    actions = _l(_d(item.get("question_context")).get("likely_actions"))
    return str(actions[0]) if actions else None


def _label(item: Mapping[str, object]) -> str:
    health = _d(item.get("health"))
    return _s(health.get("label"), _s(item.get("subject_kind")))


def render_waiting(view: Mapping[str, object], *, brief: bool = False) -> str:
    """The waiting list. ``brief``: a header and at most 8 one-line items (§5.6)."""
    value = _d(view.get("value"))
    items = [_d(i) for i in _l(value.get("items"))]
    day = value.get("today") or _local(view.get("as_of"), view.get("timezone"))[:10]
    head = f"Waiting on {day} ({len(items)} item{'s' if len(items) != 1 else ''})"
    if brief:
        lines = [head]
        for item in items[:BRIEF_MAX]:
            reasons = [_d(r) for r in _l(item.get("reasons"))]
            reason = _s(reasons[0].get("text") if reasons else None, "no reason given")
            action = _first_action(item)
            title = _cut(_s(item.get("title"), ""), _TITLE_BRIEF)
            more = f" (+{len(reasons) - 1})" if len(reasons) > 1 else ""
            line = f"{_s(item.get('position'))}. {item.get('ref')} {title} | {reason}{more}"
            lines.append(line + (f" -> {action}" if action else ""))
        if len(items) > BRIEF_MAX:
            lines.append(f"... {len(items) - BRIEF_MAX} more: coflow dec waiting")
        if not items:
            lines.append("Nothing is waiting.")
        lines.append(
            f"-- instance: {_s(view.get('instance_role'), 'unknown')} | "
            f"{_s(view.get('authority'), '')}"
        )
        return "\n".join(lines)

    lines = [head, ""]
    for item in items:
        title = _s(item.get("title"), "")
        lines.append(
            f"{_s(item.get('position'))}. {item.get('ref')}  {title}  [{_label(item)}]"
            + _authority_note(item)
        )
        qc = _d(item.get("question_context"))
        if qc.get("share_line"):
            lines.append(f"   {qc['share_line']}")
        for reason in (_d(r) for r in _l(item.get("reasons"))):
            lines.append(f"   - {_reason_line(reason)}")
        last = _d(qc.get("last_fact"))
        if last:
            age = last.get("age_days")
            age_text = f", {age} days ago" if age is not None else ""
            lines.append(
                f"   last fact {last.get('ref')}{age_text}: {_cut(_s(last.get('text'), ''), 120)}"
            )
        elif qc and item.get("subject_kind") == "decision":
            # §3.9: the context names a missing fact instead of leaving the line out.
            lines.append("   last fact: no fact recorded")
        for goal in (_d(g) for g in _l(qc.get("goals"))):
            since = f" since {goal['since']}" if goal.get("since") else ""
            lines.append(
                f"   goal {goal.get('ref')} {_s(goal.get('title'), '')}: "
                f"{_s(goal.get('status'))}{since}"
            )
        actions = [str(a) for a in _l(qc.get("likely_actions"))]
        if actions:
            lines.append("   likely: " + " | ".join(actions))
        lines.append("")
    if not items:
        lines.append("Nothing is waiting.")
        lines.append("")
    lines.extend(_footer(view))
    return "\n".join(lines)


def _reason_line(reason: Mapping[str, object]) -> str:
    text = _s(reason.get("text"), "")
    if text:
        return text
    parts = [_s(reason.get("kind"))]
    if reason.get("code"):
        parts.append(str(reason["code"]))
    if reason.get("due"):
        source = f" ({reason['due_source']})" if reason.get("due_source") else ""
        parts.append(f"due {reason['due']}{source}")
    return " ".join(parts)


# ==================================================================================================
# The card


def _when(value: object) -> str:
    when = _d(value)
    if not when or when.get("at") is None:
        return "time unknown"
    return f"{when['at']} ({_s(when.get('precision'))}, {_s(when.get('basis'))})"


def render_card(view: Mapping[str, object]) -> str:
    """``dec show``: the integrity line first when not ok, then the share line, then §5.3."""
    value = _d(view.get("value"))
    d = _d(value.get("decision"))
    health = _d(value.get("health"))
    lines: list[str] = []
    if value.get("integrity_line"):
        lines.append(f"INTEGRITY: {value['integrity_line']}")
    lines.append(_s(value.get("share_line"), "share: -"))
    lines.append(f"{d.get('public_id')}  {_s(d.get('title'), '')}")
    lines.append(
        f"health: {_s(health.get('label'))} | ground {_s(health.get('ground'))} | timeliness "
        f"{', '.join(str(t) for t in _l(health.get('timeliness'))) or '-'} | share "
        f"{_share(health.get('share'))}" + (" | bet" if health.get("bet") else "")
    )
    for reason in (_d(r) for r in _l(health.get("reasons"))):
        lines.append(f"  - {_health_reason(reason)}")
    if health.get("badge"):
        lines.append(f"  outcome: {health['badge']}")
    lines.append(
        f"status {_s(d.get('status'))} | kind {_s(d.get('kind'))} | depth {_s(d.get('depth'))} | "
        f"review {_s(d.get('review_due'))} | edition {_edition_label(d.get('current_edition'))}"
    )
    for key, label in (("question", "question"), ("statement", "statement")):
        if d.get(key):
            lines.append(f"{label}: {d[key]}")
    if d.get("success_criterion"):
        lines.append(f"success: {d['success_criterion']}")
    waiting = [_d(r) for r in _l(value.get("waiting_reasons"))]
    if waiting:
        lines.append("why it waits:")
        lines.extend(f"  - {_reason_line(r)}" for r in waiting)
    qc = _d(value.get("question_context"))
    actions = [str(a) for a in _l(qc.get("likely_actions"))]
    if actions:
        lines.append("likely: " + " | ".join(actions))
    assumptions = [_d(a) for a in _l(value.get("assumptions"))]
    if assumptions:
        lines.append("assumptions:")
        for a in assumptions:
            due = _d(a.get("due"))
            due_text = (
                f"due {due['date']} ({_s(due.get('source'))})" if due.get("date") else "no due date"
            )
            critical = "critical" if a.get("critical") else "not critical"
            lines.append(f"  {a.get('code')} [{_s(a.get('state'))}] {_s(a.get('statement'), '')}")
            threshold = _d(a.get("threshold"))
            if threshold.get("text") or threshold.get("comparator"):
                rule = _s(threshold.get("text"), "") or (
                    f"{_s(a.get('metric'), '')} {threshold.get('comparator')} "
                    f"{_s(threshold.get('value'), '')} {_s(threshold.get('unit'), '')}".strip()
                )
                lines.append(f"      threshold: {rule}")
            source = _d(a.get("data_source"))
            lines.append(f"      {due_text} | {critical} | source {_s(source.get('kind'))}")
            last = _d(a.get("last_check"))
            if last:
                lines.append(
                    f"      last check {last.get('code')}: {_s(last.get('state'))} "
                    f"{_when(last.get('observed'))}"
                )
    for key, label in (("ground_facts", "ground facts"), ("monitoring_facts", "monitoring facts")):
        facts = [_d(f) for f in _l(value.get(key))]
        if facts:
            lines.append(f"{label}:")
            for f in facts:
                when = _d(f.get("occurred")).get("at")
                text = _cut(_s(f.get("text"), ""), 160)
                lines.append(f"  {f.get('code')} {_s(when, 'time unknown')}: {text}")
    reviews = [_d(r) for r in _l(value.get("reviews"))]
    if reviews:
        lines.append("reviews:")
        for r in reviews:
            nxt = f" -> next {r['next_review_due']}" if r.get("next_review_due") else ""
            lines.append(
                f"  {r.get('code')} {_s(r.get('action'))} {_when(r.get('occurred'))}{nxt}"
                + (f": {r['verdict']}" if r.get("verdict") else "")
            )
    outcome = _d(value.get("outcome"))
    if outcome:
        lines.append(f"outcome: {_s(outcome.get('kind'))} ({_s(outcome.get('basis'))})")
    learnings = [_d(lr) for lr in _l(value.get("learnings"))]
    if learnings:
        lines.append("learnings:")
        for lr in learnings:
            text = lr.get("confirmed") or lr.get("legacy_text") or lr.get("next_step")
            lines.append(f"  {lr.get('code')}: {_cut(_s(text, ''), 160)}")
    stakes = [_d(s) for s in _l(value.get("stakes"))]
    if stakes:
        lines.append("stakes:")
        for s in stakes:
            amount = (
                "amount withheld"
                if s.get("amount_withheld")
                else (f"{_s(s.get('amount'), '')} {_s(s.get('currency'), '')}".strip() or "-")
            )
            lines.append(f"  {_s(s.get('type'))} {_s(s.get('direction'))}: {amount}")
    editions = [_d(e) for e in _l(value.get("editions"))]
    if editions:
        lines.append(
            "editions: "
            + ", ".join(
                f"{_edition_label(e.get('edition'))} {_s(e.get('status'))}"
                + (f" {e['seal12']}" if e.get("seal12") else "")
                for e in editions
            )
        )
    links = [_d(lk) for lk in _l(value.get("links")) if not _d(lk).get("removed")]
    if links:
        lines.append(
            "links: " + ", ".join(f"{lk.get('role')} {lk.get('target_ref')}" for lk in links)
        )
    execution = _d(value.get("execution"))
    for kind, counts in sorted(execution.items()):
        c = _d(counts)
        lines.append(
            f"execution ({kind}): total {c.get('total', 0)}, open {c.get('open', 0)}, "
            f"done {c.get('done', 0)}, overdue {c.get('overdue', 0)}"
        )
    authority = _d(value.get("authority"))
    lines.append(f"mirror: {_s(value.get('mirror_line'), _s(authority.get('text')))}")
    lines.extend(_footer(view))
    return "\n".join(lines)


def _health_reason(reason: Mapping[str, object]) -> str:
    """A health reason in words, with its date and the date's source unless the words say them."""
    text = _s(reason.get("text"), "")
    day, source = reason.get("day"), reason.get("source")
    parts = [] if not day or str(day) in text else [str(day)]
    if source and str(source) not in text:
        parts.append(f"from {source}")
    return text + (f" ({', '.join(parts)})" if parts else "")


def _edition_label(edition: object) -> str:
    return f"E-{edition:02d}" if isinstance(edition, int) else _s(edition)


# ==================================================================================================
# List, integrity, shadow, import, token


def render_list(view: Mapping[str, object]) -> str:
    value = _d(view.get("value"))
    lines = []
    for line in (_d(x) for x in _l(value.get("lines"))):
        mirror = f"  [{line['mirror_of']}]" if line.get("mirror_of") else ""
        lines.append(
            f"{line.get('public_id')}  {_cut(_s(line.get('title'), ''), 48)}  "
            f"{_s(line.get('label'))}  share {_share(line.get('share'))}  "
            f"review {_s(line.get('review_due'))}  {_s(line.get('first_reason'), '')}".rstrip()
            + mirror
        )
    if not lines:
        lines.append("No decisions match.")
    lines.append(f"({value.get('count', 0)} decisions)")
    lines.extend(_footer(view))
    return "\n".join(lines)


def render_integrity(view: Mapping[str, object]) -> str:
    value = _d(view.get("value"))
    lines = []
    for report in (_d(r) for r in _l(value.get("reports"))):
        status = "ok" if report.get("ok") else "NOT OK"
        lines.append(f"{report.get('decision_ref')}: {status}")
        for line in (_d(x) for x in _l(report.get("lines"))):
            items = (
                f" ({', '.join(str(i) for i in _l(line.get('items')))})"
                if _l(line.get("items"))
                else ""
            )
            seal = f" seal {line['seal12']}" if line.get("seal12") else ""
            lines.append(
                f"  {_edition_label(line.get('edition'))}: {_s(line.get('status'))}{seal}{items}"
            )
    if not lines:
        lines.append("No decisions to check.")
    lines.extend(_footer(view))
    return "\n".join(lines)


def render_shadow(view: Mapping[str, object]) -> str:
    """``dec shadow``: totals per class, every unexpected line with both values (§5.6)."""
    value = _d(view.get("value"))
    totals = _d(value.get("totals"))
    lines = [
        f"Shadow report, run {value.get('run_id')} (snapshot as of {_s(value.get('as_of_date'))}): "
        f"{_s(value.get('report_status'))}",
        "totals: "
        + ", ".join(
            f"{k} {totals[k]}" for k in ("same", "expected", "unexpected", "finding") if k in totals
        ),
    ]
    by_rule = _d(value.get("by_rule"))
    if by_rule:
        lines.append("expected by rule: " + ", ".join(f"{k} {v}" for k, v in by_rule.items()))
    unexpected = [_d(i) for i in _l(value.get("unexpected"))]
    if unexpected:
        lines.append("unexpected:")
        lines.extend(_shadow_lines(unexpected))
    findings = [_d(i) for i in _l(value.get("findings"))]
    if findings:
        lines.append("findings:")
        lines.extend(_shadow_lines(findings))
    runs = value.get("runs_since_last_unexpected")
    if runs is not None:
        lines.append(f"clean runs in a row: {runs}")
    lines.extend(_footer(view))
    return "\n".join(lines)


def _shadow_lines(items: Iterable[Mapping[str, object]]) -> list[str]:
    out = []
    for i in items:
        subject = f" {i['subject_ref']}" if i.get("subject_ref") else ""
        out.append(
            f"  {i.get('decision_ref')}{subject} {i.get('aspect')}: V1 {_s(i.get('v1_value'))} | "
            f"v2 {_s(i.get('v2_value'))}"
        )
    return out


def render_import(view: Mapping[str, object]) -> str:
    value = _d(view.get("value"))
    dry_run = value.get("mode") == "dry_run"
    source = (
        f"(mode {_s(value.get('mode'))}, from {_s(value.get('source_issuer'))}"
        f"{', synthetic' if value.get('synthetic') else ''})"
    )
    if dry_run:
        # A dry run validates and plans only; DEC reports it as a no-op because it writes nothing
        # (integration: it is not "already applied").
        head = f"Dry run {source}: nothing was written; the counts are what an import would do."
    else:
        head = f"Import run {_s(value.get('run_id'))}: {_s(value.get('status'))} {source}"
    lines = [head]
    if value.get("noop") and not dry_run:
        # The counts of a no-op are those of the run that applied the file (§6.5), so say so:
        # "new 96" under a no-op would otherwise read as 96 new rows.
        lines.append(
            f"This snapshot was already applied by run {_s(value.get('run_id'))}: nothing "
            "changed. The counts below are that run's."
        )
    for entity, counts in _d(value.get("counts")).items():
        c = _d(counts)
        lines.append(
            f"  {entity}: seen {c.get('seen', 0)}, new {c.get('new', 0)}, "
            f"changed {c.get('changed', 0)}, unchanged {c.get('unchanged', 0)}, "
            f"absent {c.get('absent', 0)}"
        )
    if _l(value.get("absent")):
        lines.append("absent since this run: " + ", ".join(str(a) for a in _l(value.get("absent"))))
    lines.extend(f"finding: {f}" for f in _l(value.get("findings")))
    if not dry_run:
        lines.append(f"shadow report: {_s(value.get('report_status'))} (coflow dec shadow)")
    lines.append(
        f"-- instance: {_s(view.get('instance_role'), 'unknown')} | {_s(view.get('authority'), '')}"
    )
    return "\n".join(lines)


def render_token(view: Mapping[str, object]) -> str:
    value = _d(view.get("value"))
    scope = _s(value.get("scope"))
    lines = [
        f"{'Replaced the token' if value.get('replaced') else 'New token'} for MCP client "
        f"{value.get('client')} (actor {value.get('actor')}, scope {scope}, financial "
        f"{'on' if value.get('financial') else 'off'}):",
        f"  {value.get('token')}",
        "It is shown once; CoFlow stores only its hash."
        + (" The previous token no longer works." if value.get("replaced") else ""),
        "Local AI client: run `coflow mcp-stdio` with the environment variable "
        "COFLOW_MCP_TOKEN set to this token, while `coflow run` serves the instance.",
        f"-- instance: {_s(view.get('instance_role'), 'unknown')}",
    ]
    return "\n".join(lines)


def render_view(view: Mapping[str, object], *, brief: bool = False) -> str:
    """Any view by its ``view`` name."""
    kind = view.get("view")
    if "error" in view:
        return render_error(view)
    renderers = {
        "decision_context": render_card,
        "decision_list": render_list,
        "integrity": render_integrity,
        "shadow_report": render_shadow,
        "import_report": render_import,
        "mcp_token": render_token,
    }
    if kind == "waiting":
        return render_waiting(view, brief=brief)
    if kind == "ping":
        return f"core is running | instance: {view.get('instance_role')}"
    renderer = renderers.get(str(kind))
    if renderer is None:
        raise ValueError(f"no renderer for view {kind!r}")
    return renderer(view)


# ==================================================================================================
# Kernel reports


def render_init(info: InstanceInfo, data_root: Path, *, timezone: str) -> str:
    return "\n".join(
        [
            f"Initialised a {info.role} instance {info.instance_id} in {data_root}",
            f"  owner zone {timezone}",
            "Next: coflow doctor, then coflow run (or any coflow dec command).",
        ]
    )


def render_doctor(report: DoctorReport) -> str:
    lines = [f"coflow doctor: {report.data_root}"]
    for check in report.checks:
        mark = "ok  " if check.ok else "FAIL"
        detail = check.detail
        if detail.startswith(f"{check.name}: "):
            detail = detail[len(check.name) + 2 :]
        lines.append(f"  [{mark}] {check.name}" + (f": {detail}" if detail else ""))
    lines.append("all checks passed" if report.ok else "some checks failed")
    return "\n".join(lines)


# ==================================================================================================
# The morning pull (§5.6)

_WINDOWS_TASK = (
    'schtasks /Create /SC DAILY /ST 08:00 /TN "CoFlow morning pull" '
    '/TR "cmd /k coflow dec waiting --brief --data-root \\"{data_root}\\""'
)
_CRON_LINE = (
    '0 8 * * * COFLOW_DATA_ROOT="{data_root}" '
    'notify-send "CoFlow: waiting" "$(coflow dec waiting --brief)"'
)

MORNING_PULL_RECIPE = "\n".join(
    [
        "The morning pull: v2 cannot push anything before the bot exists (stage 2), so the",
        "waiting list is pulled once a day. Every pull is counted as a usage signal by",
        "channel (cli, mcp), so real daily use is measurable from the first week.",
        "",
        "1. From the operating system's scheduler, a window with the brief list every",
        "   morning at 08:00 (it stays open until you close it):",
        "",
        "   Windows (Task Scheduler):",
        "     " + _WINDOWS_TASK,
        "",
        "   Linux (crontab -e; needs a desktop notification daemon):",
        "     " + _CRON_LINE,
        "",
        "2. Or from an AI client that runs scheduled prompts, with the coflow-v2 server",
        "   connected (coflow mcp-stdio):",
        "",
        '     Every morning at 08:00: "Call the dec_waiting tool of the coflow-v2 server and',
        "     show me the list exactly as it comes back, one line per item, with the reason",
        '     and the likely first action. Do not change anything."',
        "",
        "The brief list shows at most 8 items, one line each: the ref, the title, the first",
        "reason (and how many more) and the likely first action. The full list with every",
        "reason and its question context: coflow dec waiting. One decision: coflow dec show REF.",
        "",
    ]
)


def render_recipe(data_root: Path | None) -> str:
    return MORNING_PULL_RECIPE.format(data_root=str(data_root) if data_root else "<DATA_ROOT>")
