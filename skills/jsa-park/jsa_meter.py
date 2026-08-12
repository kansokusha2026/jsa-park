#!/usr/bin/env python3
"""jsa_meter.py — show, in numbers, what parking a session actually saved.

Part of jsa-park (https://github.com/kansokusha2026/jsa-park).
Reads local Claude Code transcripts (~/.claude/projects/) only.
No network access, no dependencies beyond the standard library.

Modes:
  park     Stamp RESUME.md with the parked session's final context size.
           Run from inside the session being parked (jsa-park, step 3).
  resume   Compare that stamp against the fresh session's cold start and
           print a savings report (jsa-resume shows it to the user).

The report uses model-agnostic rate weights, expressed in
"input-token equivalents" (eq): a 1h-cache write costs about 2.0x the
base input rate, a cache read about 0.1x. No prices are assumed.
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

WRITE_1H = 2.0  # 1h ephemeral cache write ~= 2.0x base input rate
READ = 0.1      # cache read ~= 0.1x base input rate

STAMP_RE = re.compile(r"<!--\s*jsa-park-meter:\s*(\{.*?\})\s*-->", re.S)


def project_dir(cwd: Path) -> Path:
    """Map a working directory to its Claude Code transcript folder."""
    munged = re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))
    return Path.home() / ".claude" / "projects" / munged


def session_files(pdir: Path):
    return sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


def usages(path: Path):
    """(timestamp, usage) for every assistant message in a transcript."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if j.get("type") != "assistant":
                continue
            u = (j.get("message") or {}).get("usage")
            if u and "input_tokens" in u:
                out.append((j.get("timestamp"), u))
    return out


def ctx(u):
    """Total context registered for one request."""
    return (u.get("input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0))


def fmt(n):
    return f"{n:,.0f}"


def find_current_session(pdir: Path):
    files = session_files(pdir)
    if not files:
        sys.exit(f"jsa_meter: no transcripts found under {pdir}")
    return files[-1]


def cmd_park(args):
    current = find_current_session(project_dir(Path.cwd()))
    us = usages(current)
    if not us:
        sys.exit(f"jsa_meter: no usage records in {current.name}")
    _, last = us[-1]
    stamp = {
        "session": current.stem,
        "parked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "context_tokens": ctx(last),
        "requests": len(us),
    }
    line = f"<!-- jsa-park-meter: {json.dumps(stamp)} -->"
    print(f"parked session : {current.stem[:8]}  "
          f"context {fmt(stamp['context_tokens'])} tokens after {len(us)} requests")
    if args.write:
        note = Path(args.resume_file)
        if not note.exists():
            sys.exit(f"jsa_meter: {note} not found — write RESUME.md first, then stamp it")
        text = STAMP_RE.sub("", note.read_text(encoding="utf-8")).rstrip("\n")
        note.write_text(text + "\n\n" + line + "\n", encoding="utf-8")
        print(f"stamp written to {note}")
    else:
        print("append this line to RESUME.md (or re-run with --write):")
        print(line)


def cmd_resume(args):
    note = Path(args.resume_file)
    if not note.exists():
        sys.exit(f"jsa_meter: {note} not found")
    m = STAMP_RE.search(note.read_text(encoding="utf-8"))
    if not m:
        print("jsa_meter: no park stamp in the note — nothing to compare. "
              "(Notes built by jsa_handoff.py, or parked before the meter "
              "existed, have no stamp.)")
        return
    stamp = json.loads(m.group(1))
    current = find_current_session(project_dir(Path.cwd()))
    if current.stem == stamp["session"]:
        print("jsa_meter: this IS the parked session — the meter only makes "
              "sense from a fresh session. Nothing to compare.")
        return
    us = usages(current)
    if not us:
        sys.exit(f"jsa_meter: no usage records yet in {current.name}")
    _, first = us[0]
    c_old = stamp["context_tokens"]
    c_new = ctx(first)
    saved = c_old - c_new

    parked_at = datetime.datetime.fromisoformat(stamp["parked_at"])
    gap = datetime.datetime.now().astimezone() - parked_at
    gap_h = gap.total_seconds() / 3600

    print("=== jsa-park savings meter ===")
    print(f"parked session : {stamp['session'][:8]}  "
          f"context {fmt(c_old)} tokens after {stamp['requests']} requests "
          f"({parked_at.strftime('%Y-%m-%d %H:%M')})")
    print(f"fresh session  : {current.stem[:8]}  "
          f"cold start registered {fmt(c_new)} tokens")
    print(f"break length   : {gap_h:.1f} h")
    if saved <= 0:
        print("context did not shrink — the fresh session started as large "
              "as the parked one ended. No savings to report.")
        return
    pct = 100.0 * saved / c_old
    print(f"context shed   : {fmt(saved)} tokens (-{pct:.0f}%) — "
          f"conversation history replaced by the handoff note")
    print(f"estimated savings (rate weights: 1h-cache write x{WRITE_1H}, "
          f"cache read x{READ}):")
    print(f"  per cold restart after a 1h+ break : "
          f"~{fmt(saved * WRITE_1H)} input-token eq avoided")
    print(f"  per message from now on            : "
          f"~{fmt(saved * READ)} input-token eq lighter "
          f"(vs. continuing the old session)")
    if gap_h < 1.0:
        print(f"note: the break was only {gap_h:.1f} h, so the old cache was "
              f"likely still warm — this restart itself was not the saving. "
              f"The numbers above apply to every 1h+ break avoided from here on.")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("park", help="stamp RESUME.md with this session's final context size")
    p.add_argument("--resume-file", default="RESUME.md")
    p.add_argument("--write", action="store_true",
                   help="append the stamp to the note (default: print only)")
    p.set_defaults(func=cmd_park)
    r = sub.add_parser("resume", help="print the savings report for a fresh session")
    r.add_argument("--resume-file", default="RESUME.md")
    r.set_defaults(func=cmd_resume)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
