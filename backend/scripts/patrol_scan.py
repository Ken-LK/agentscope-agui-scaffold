"""SLS patrol scan: window aggregate → structured report → auto-drill Redis (read-only).

Companion to patrol_session.py (single-session drill), forming a "scan → drill →
report" set.

What it does (envelope-only — the scaffold does not understand domain fields):
1. Pull all logs in the window, count by event/type, bucket real traffic vs noise
   (test/eval/smoke fixtures) via a positive nanoid whitelist.
2. Mark deploy boundaries (smoke run_ids) — across a deploy, old code lacks new
   fields; that is not a bug.
3. Link integrity self-check: input_text / output_text / reasoning_steps fill rate
   on real agent_run records.
4. Anomaly scan: error_code set, or any tool_call with status ≠ ok.
5. Feedback link summary.
6. Auto-drill: for real anomaly runs, pull the Redis scene by thread_id + user_id
   (desensitized by default, capped by --max-drill).

Read-only. Never prints AK/SK. Redis drill desensitized by default.

Usage (.venv interpreter):
    cd backend && .venv/bin/python scripts/patrol_scan.py --since 1h
    cd backend && .venv/bin/python scripts/patrol_scan.py --since 11:33
    cd backend && RU='redis://:***@redis.example.com:6379/0' \
      .venv/bin/python scripts/patrol_scan.py --since 11:33 --redis-url "$RU"
"""

from __future__ import annotations

import argparse
import ast
import datetime
import json
import os
import re
import sys
import time
from collections import defaultdict

from app.core.settings import get_settings

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Incremental watermark: remember the window end; --since last resumes from it.
_WATERMARK = os.path.join(_BACKEND, ".patrol_watermark.json")
# Report archive (markdown, gitignored; drills hold desensitized PII, local-only).
_REPORTS_DIR = os.path.join(_BACKEND, ".patrol_reports")

# A real deployed ag-ui runId is a hyphen-free nanoid (cZzfEOW / 0L4pkkR); all
# test/eval/smoke fixtures carry a hyphen or dot. A positive whitelist (nanoid shape
# is stable) beats a blacklist of prefixes, which fixtures always outgrow.
_NANOID = re.compile(r"[A-Za-z0-9]{5,20}")
# Deploy-boundary heuristic: run_ids from smoke/deploy fixtures (project may extend).
_DEPLOY_PREFIXES = ("deploy-smoke", "smoke", "route-valid")


def _read_watermark() -> int | None:
    try:
        with open(_WATERMARK, encoding="utf-8") as f:
            return int(json.load(f)["last_to"])
    except (OSError, ValueError, KeyError):
        return None


def _write_watermark(to: int) -> None:
    with open(_WATERMARK, "w", encoding="utf-8") as f:
        json.dump({"last_to": int(to),
                   "last_to_iso": datetime.datetime.fromtimestamp(to).isoformat()}, f)


def _is_noise(run_id: str) -> bool:
    return not (run_id and _NANOID.fullmatch(run_id))


def _pl(v):
    try:
        return ast.literal_eval(v) if v else []
    except (ValueError, SyntaxError):
        return []


def _parse_since(s: str, now: int) -> int:
    """'90m'/'2h' relative; '11:33' today local; bare digits epoch."""

    s = s.strip()
    m = re.fullmatch(r"(\d+)([mh])", s)
    if m:
        n = int(m.group(1))
        return now - n * (60 if m.group(2) == "m" else 3600)
    m = re.fullmatch(r"(\d{1,2}):(\d{2})", s)
    if m:
        t = datetime.time(int(m.group(1)), int(m.group(2)))
        return int(datetime.datetime.combine(datetime.date.today(), t).timestamp())
    if s.isdigit():
        return int(s)
    raise SystemExit(f"cannot parse --since={s!r} (use '1h'/'30m'/'11:33'/epoch)")


def _pull(client, project, logstore, frm, now):
    from aliyun.log import GetLogsRequest  # noqa: PLC0415

    items, off = [], 0
    while True:
        logs = client.get_logs(
            GetLogsRequest(project=project, logstore=logstore, fromTime=frm,
                           toTime=now, query="*", line=100, offset=off, reverse=True)
        ).get_logs()
        if not logs:
            break
        items += logs
        off += len(logs)
        if len(logs) < 100 or off >= 5000:
            break
    return items


def _hm(t: int) -> str:
    return datetime.datetime.fromtimestamp(t).strftime("%H:%M:%S")


def _fmt(t: int) -> str:
    """Time with date (a window may span days; bare HH:MM is ambiguous)."""

    return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M:%S")


def _clean1(s: str, n: int) -> str:
    """Question/answer summary cleanup: strip markdown, fold whitespace, truncate."""

    s = re.sub(r"[*#`>]+", "", s or "")
    s = re.sub(r"\s+", " ", s).strip()
    return s[:n] + ("…" if len(s) > n else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="SLS patrol scan (read-only, auto-drill Redis)")
    ap.add_argument("--since", default="1h",
                    help="window start: last / 1h / 30m / 11:33 / epoch (default 1h)")
    ap.add_argument("--to", default="", help="window end epoch (default now)")
    ap.add_argument("--redis-url", default="", help="drill Redis (default backend settings; remote → pass this)")
    ap.add_argument("--max-drill", type=int, default=3, help="max anomaly auto-drills (default 3)")
    ap.add_argument("--no-drill", action="store_true", help="scan SLS only, no Redis drill")
    ap.add_argument("--no-watermark", action="store_true", help="do not advance watermark (ad-hoc query)")
    ap.add_argument("--max-convos", type=int, default=10, help="max real conversations shown (default 10)")
    ap.add_argument("--no-convos", action="store_true", help="do not show real conversations")
    ap.add_argument("--out", default="", help="write report to path (default .patrol_reports/patrol-<time>.md)")
    ap.add_argument("--no-save", action="store_true", help="do not archive report, terminal only")
    ap.add_argument("--raw", action="store_true", help="drill without desensitization (careful)")
    args = ap.parse_args()

    s = get_settings()
    if not (s.sls_enabled and s.sls_endpoint and s.sls_access_key_id and s.sls_project):
        raise SystemExit("SLS not configured (set sls_enabled + endpoint/keys/project). See settings.")
    from aliyun.log import LogClient  # noqa: PLC0415

    client = LogClient(s.sls_endpoint, s.sls_access_key_id, s.sls_access_key_secret)
    now = int(args.to) if args.to else int(time.time())
    if args.since == "last":
        wm = _read_watermark()
        frm = wm if wm is not None else now - 3600
        since_note = f"resume watermark {_fmt(wm)}" if wm is not None else "no watermark → last 1h"
    else:
        frm = _parse_since(args.since, now)
        since_note = f"--since {args.since}"

    items = _pull(client, s.sls_project, s.sls_logstore, frm, now)
    rows = [(it.get_time(), it.get_contents()) for it in items]

    def cat(d):
        return d.get("event") or d.get("type") or "(none)"

    runs = [(t, d) for t, d in rows if cat(d) == "agent_run"]
    fbs = [d for _, d in rows if cat(d) == "feedback"]
    real = [(t, d) for t, d in runs if not _is_noise(d.get("run_id", ""))]
    noise_n = len(runs) - len(real)

    deploy_marks = sorted(
        _hm(t) + " " + d.get("run_id", "") for t, d in rows
        if str(d.get("run_id", "")).startswith(_DEPLOY_PREFIXES)
    )

    # Integrity self-check (real agent_run)
    real_n = len(real)
    fill = {k: sum(1 for _, d in real if d.get(k)) for k in ("input_text", "output_text", "reasoning_steps")}
    if not real_n:
        cmpl = ""
    elif all(v == real_n for v in fill.values()):
        cmpl = "all filled"
    elif all(v == 0 for v in fill.values()):
        cmpl = "⚠️ all empty (capture regression)"
    elif deploy_marks and max(fill.values()) < real_n:
        cmpl = "partial (across deploy boundary, old code lacks new fields; expected)"
    else:
        cmpl = "⚠️ uneven fill, not just a deploy boundary — check specific field capture"

    # Anomalies + tool link: real traffic only
    anomalies = []  # (t, d, reason)
    tool_runs = tool_bad = 0
    for t, d in real:
        ec = d.get("error_code", "")
        tcs = _pl(d.get("tool_calls", ""))
        bad = [c for c in tcs if isinstance(c, dict) and c.get("status") not in ("ok", "skipped", None)]
        if ec:
            anomalies.append((t, d, f"error_code={ec}"))
        if tcs:
            tool_runs += 1
        if bad:
            tool_bad += 1
            names = ",".join(str(c.get("name")) for c in bad)
            anomalies.append((t, d, f"tool_status≠ok: {names}"))

    # Feedback link
    real_run_ids = {d.get("run_id") for _, d in runs if d.get("run_id")}
    fb_linked = sum(1 for d in fbs if d.get("run_id") in real_run_ids)

    # ── report ────────────────────────────────────────────────────────
    out = []
    out.append(f"# SLS Patrol Report — {datetime.datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M')}")
    out.append(f"window: {_fmt(frm)} → {_fmt(now)}  ({since_note})  |  source: settings + SDK full scan")
    out.append(f"deploy boundary: {('; '.join(deploy_marks)) if deploy_marks else 'none in window'}")
    out.append("\n## Traffic")
    out.append(f"total {len(rows)} | agent_run {len(runs)} (real {real_n} / noise {noise_n}) "
               f"| feedback {len(fbs)}")
    out.append("\n## Link integrity self-check (real agent_run)")
    if real_n:
        out.append(f"input_text {fill['input_text']}/{real_n} · output_text {fill['output_text']}/{real_n} "
                   f"· reasoning_steps {fill['reasoning_steps']}/{real_n}  → {cmpl}")
    else:
        out.append("no real agent_run in window, skipped.")
    out.append("\n## Anomaly runs")
    if anomalies:
        out.append("time | run_id | reason")
        for t, d, why in sorted(anomalies, key=lambda x: x[0], reverse=True):
            out.append(f"{_fmt(t)} | {d.get('run_id')} | {why}")
    else:
        out.append("none.")
    out.append("\n## Tool link")
    out.append(f"runs with tool calls {tool_runs} | runs with status≠ok {tool_bad}")
    out.append("\n## Feedback link")
    out.append(f"feedback {len(fbs)} | linked to real run in window {fb_linked}")

    # Verdict heuristic. FAIL only when a real run has error_code, or all new fields
    # are empty (capture regression). Partial fill is a deploy boundary, not a fail.
    fail = bool([a for a in anomalies if a[2].startswith("error_code=")]) \
        or bool(real_n and all(fill[k] == 0 for k in fill))
    warn = bool(anomalies or tool_bad or (fbs and not fb_linked)
                or (real_n and cmpl.startswith("⚠️")))
    verdict = "FAIL" if fail else ("WARN" if warn else "PASS")
    out.append("\n## Verdict")
    out.append(f"{verdict}  |  real traffic {real_n} turns, {len(anomalies)} anomalies.")

    # ── assessment (translate metrics into judgement) ──
    asmt: list[str] = []
    if real_n == 0:
        asmt.append("no real user traffic in window (all test/eval/smoke fixtures); verdict is of limited value.")
    elif cmpl == "all filled":
        asmt.append(f"capture complete: question/answer/reasoning landed for all {real_n} real turns.")
    elif cmpl.startswith("partial"):
        asmt.append(f"new fields partially filled ({fill['input_text']}/{real_n}), matches a deploy boundary in window; expected.")
    else:
        asmt.append(f"⚠️ {cmpl}: input {fill['input_text']}/output {fill['output_text']}/"
                    f"reasoning {fill['reasoning_steps']}, of {real_n} turns.")
    if tool_runs and tool_bad:
        asmt.append(f"{tool_bad}/{tool_runs} tool-call turns reported status≠ok, auto-drilled below.")
    elif tool_runs:
        asmt.append(f"tool link healthy: all {tool_runs} tool-call turns status=ok.")
    if not anomalies:
        asmt.append("no anomaly runs.")
    if 0 < real_n < 5:
        asmt.append(f"small sample ({real_n} turns); local judgement, re-patrol after more traffic.")

    # ── suggestions (only when actually triggered) ──
    sug: list[str] = []
    if tool_bad:
        sug.append("tool status≠ok: drill to confirm whether the tool genuinely failed/degraded vs a status-mapping bug.")
    if real_n and cmpl.startswith("⚠️"):
        sug.append(f"integrity {cmpl}: field-by-field check capture (input_text often empty on image/empty-text turns).")
    if fbs and not fb_linked:
        sug.append(f"feedback {len(fbs)} all unlinked to a real run: mostly fixtures; if real, trace feedback run_id propagation.")
    if not sug:
        sug.append("no triggers, no optimization needed, keep current observation.")

    out.append("\n## Assessment")
    out.extend("- " + a for a in asmt)
    out.append("\n## Suggestions")
    out.extend("- " + a for a in sug)

    # ── real conversations (who asked / how it answered; from SLS, desensitized) ──
    if not args.no_convos and real:
        convos: dict = defaultdict(list)
        for t, d in real:
            convos[(d.get("user_id", ""), d.get("thread_id", ""))].append((t, d))
        ordered = sorted(convos.items(), key=lambda kv: max(t for t, _ in kv[1]), reverse=True)
        out.append(f"\n## Real conversations ({len(ordered)} sessions)")
        for (uid, tid), turns in ordered[:args.max_convos]:
            turns.sort(key=lambda x: x[0])
            out.append(f"\n### 👤 {uid or '(empty)'} · thread {tid[:8]} · {len(turns)} turns")
            for i, (t, d) in enumerate(turns, 1):
                out.append(f"{i}. `{_hm(t)}`")
                out.append(f"    - Q: {_clean1(d.get('input_text') or '(no text / attachment turn)', 70)}")
                out.append(f"    - A: {_clean1(d.get('output_text'), 120)}")
        if len(ordered) > args.max_convos:
            out.append(f"\n({len(ordered) - args.max_convos} more sessions; raise --max-convos)")

    buf: list[str] = []

    def emit(line: str = "") -> None:
        print(line)
        buf.append(line)

    emit("\n".join(out))

    # Advance watermark: next --since last resumes from this end (no gaps/dupes).
    if not args.no_watermark:
        _write_watermark(now)
        emit(f"\nwatermark advanced → {_fmt(now)} ({now}). next: patrol_scan.py --since last")
    else:
        emit("\n(--no-watermark: watermark not advanced)")

    # ── anomaly auto-drill into Redis scene ───────────────────────────
    real_anoms = [(t, d, why) for t, d, why in anomalies if not _is_noise(d.get("run_id", ""))]
    if not args.no_drill and real_anoms:
        emit(f"\n{'='*66}\n## Anomaly drill (Redis scene, read-only, desensitized by default)")
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from patrol_session import load_session, render_session_lines  # noqa: PLC0415

        redis_url = args.redis_url or s.redis_url
        seen: set = set()
        drilled = 0
        for t, d, why in sorted(real_anoms, key=lambda x: x[0], reverse=True):
            rid = d.get("run_id")
            if rid in seen:
                continue
            seen.add(rid)
            if drilled >= args.max_drill:
                emit(f"\n(reached --max-drill={args.max_drill}, {len(real_anoms)-drilled} anomalies not drilled)")
                break
            drilled += 1
            uid, tid = d.get("user_id", ""), d.get("thread_id", "")
            emit(f"\n▶ {rid}  [{why}]  user={uid} thread={tid}")
            try:
                state, _ttl, _key = load_session(uid, tid, redis_url)
            except Exception as e:  # noqa: BLE001
                emit(f"   [Redis drill failed] {type(e).__name__}: {str(e)[:80]}")
                continue
            if state is None:
                emit("   [not found] TTL expired or scope mismatch → fall back to SLS input_text/output_text.")
                continue
            for line in render_session_lines(state, args.raw, max_chars=400):
                emit("   " + line)
        if not args.raw:
            emit("\n(drill desensitized; holds PII, read-only check, do not export)")
    elif args.no_drill and real_anoms:
        emit(f"\n(--no-drill: skipped Redis drill of {len(real_anoms)} real anomalies)")

    # Archive report (markdown); gitignored, drills hold desensitized PII, local-only.
    if not args.no_save:
        path = args.out or os.path.join(
            _REPORTS_DIR, "patrol-" + datetime.datetime.fromtimestamp(now).strftime("%Y%m%d-%H%M%S") + ".md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(buf) + "\n")
        print(f"\n📄 report saved → {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
