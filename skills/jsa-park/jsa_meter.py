#!/usr/bin/env python3
"""jsa_meter.py — show, in numbers, what parking a session actually saved.

Part of jsa-park (https://github.com/kansokusha2026/jsa-park).
Reads local Claude Code transcripts (~/.claude/projects/) only.
No network access, no dependencies beyond the standard library.

Modes:
  park     Stamp RESUME.md with the parked session's final context size,
           and record where the note was written.
           Run from inside the session being parked (jsa-park, step 3).
  locate   Print the path of the note parked from this launch directory
           (jsa-resume, step 1). The note may live in a subfolder — a
           monorepo package, a vault project — not only in the folder
           Claude Code was started in.
  resume   Compare that stamp against the fresh session's cold start and
           print a savings report (jsa-resume shows it to the user).

Sessions are identified by CLAUDE_CODE_SESSION_ID when Claude Code sets
it, so a `cd` earlier in the session does not change the answer; without
it, the newest transcript for the current directory is used.

The report is in "input-token equivalents" (eq), not money: a 1h cache
write costs about 2.0x the base input rate, and a cache read about 0.1x
on most models but 0.05x on Claude Opus 5.5 and 0.025x on Claude Fable 5.1. The read weight is taken
from the model the fresh session is actually using, read out of the
transcript. Override either weight with --cache-read-rate /
--cache-write-rate. No prices are assumed.
"""

import argparse
import datetime
import json
import os
import re
import sys
from pathlib import Path

# Rate weights relative to the base input rate.
# A 1h ephemeral cache write is ~2.0x base input on every current model.
WRITE_1H = 2.0

# Cache reads are ~0.1x base input on most models. Claude Fable 5.1 reads
# at 0.025x ($0.25 per MTok against $10 input) and Claude Opus 5.5 at 0.05x
# ($0.20 against $4), which moves the estimate enough to be worth detecting
# rather than assuming. Keyed by exact model
# id; anything absent falls back to READ_DEFAULT and says so in the report.
READ_DEFAULT = 0.1
READ_BY_MODEL = {
    "claude-fable-5-1": 0.025,
    "claude-opus-5-5": 0.05,
}

STAMP_RE = re.compile(r"<!--\s*jsa-park-meter:\s*(\{.*?\})\s*-->", re.S)

PROJECTS = Path.home() / ".claude" / "projects"
# Where each launch directory's last note was written, keyed by the
# transcript folder name. Local only, like everything else here.
REGISTRY = Path.home() / ".claude" / "jsa-park" / "notes.json"
NOTE_NAME = "RESUME.md"
# Fallback search when the registry has no entry (notes parked before
# the registry existed): how deep to look, and what not to walk into.
SEARCH_DEPTH = 6
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__",
             ".obsidian", ".trash"}


def project_dir(cwd: Path) -> Path:
    """Map a working directory to its Claude Code transcript folder."""
    munged = re.sub(r"[^A-Za-z0-9]", "-", str(cwd.resolve()))
    return PROJECTS / munged


def session_files(pdir: Path):
    return sorted(pdir.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)


def usages(path: Path):
    """(timestamp, usage, model) for every assistant message with usage."""
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                j = json.loads(line)
            except json.JSONDecodeError:
                continue
            if j.get("type") != "assistant":
                continue
            m = j.get("message") or {}
            u = m.get("usage")
            if u and "input_tokens" in u:
                out.append((j.get("timestamp"), u, m.get("model")))
    return out


def last_model(records):
    """Most recent real model id in a transcript, or None.

    Skips placeholders such as "<synthetic>", which Claude Code writes for
    messages that were not produced by a model.
    """
    for _, _, model in reversed(records):
        if model and not model.startswith("<"):
            return model
    return None


def read_rate(model):
    """(weight, recognised) cache-read weight for a model id."""
    if model in READ_BY_MODEL:
        return READ_BY_MODEL[model], True
    return READ_DEFAULT, False


def ctx(u):
    """Total context registered for one request."""
    return (u.get("input_tokens", 0)
            + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0))


def fmt(n):
    return f"{n:,.0f}"


def find_current_session():
    """This session's transcript.

    Prefer the session id Claude Code exports, which stays right even
    after the shell has cd'd elsewhere; fall back to the newest transcript
    for the current directory.
    """
    sid = os.environ.get("CLAUDE_CODE_SESSION_ID")
    if sid:
        hits = sorted(PROJECTS.glob(f"*/{sid}.jsonl"),
                      key=lambda p: p.stat().st_mtime)
        if hits:
            return hits[-1]
    pdir = project_dir(Path.cwd())
    files = session_files(pdir)
    if not files:
        sys.exit(f"jsa_meter: no transcripts found under {pdir}")
    return files[-1]


def read_stamp(note: Path):
    try:
        m = STAMP_RE.search(note.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError):
        return None
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def load_registry():
    try:
        return json.loads(REGISTRY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_registry(reg):
    REGISTRY.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRY.with_suffix(".tmp")
    tmp.write_text(json.dumps(reg, ensure_ascii=False, indent=2) + "\n",
                   encoding="utf-8")
    tmp.replace(REGISTRY)


def search_notes(root: Path):
    """Every RESUME.md under root, down to SEARCH_DEPTH levels."""
    root_depth = len(root.parts)
    for dirpath, dirnames, filenames in os.walk(root):
        here = Path(dirpath)
        if len(here.parts) - root_depth >= SEARCH_DEPTH:
            dirnames[:] = []
        else:
            dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        if NOTE_NAME in filenames:
            yield here / NOTE_NAME


def locate_note(pdir: Path, root: Path):
    """(note, how) for the note parked from the launch directory of pdir.

    1. the registry entry written by `park --write`;
    2. otherwise the newest stamped RESUME.md under root whose parked
       session belongs to this launch directory (notes parked before the
       registry existed);
    3. otherwise an unstamped RESUME.md in root itself (a note built by
       jsa_handoff.py after the fact).
    """
    entry = load_registry().get(pdir.name)
    if entry:
        note = Path(entry["note"])
        if note.is_file() and read_stamp(note):
            return note, "registry"
    found = []
    for note in search_notes(root):
        stamp = read_stamp(note)
        if stamp and (pdir / f"{stamp.get('session')}.jsonl").exists():
            found.append((stamp.get("parked_at", ""), note))
    if found:
        found.sort()
        return found[-1][1], "search"
    plain = root / NOTE_NAME
    if plain.is_file():
        return plain, "unstamped"
    return None, None


def cmd_locate(args):
    current = find_current_session()
    note, how = locate_note(current.parent, Path.cwd())
    if note is None:
        sys.exit(f"jsa_meter: no {NOTE_NAME} parked from this launch directory")
    print(note.resolve())
    if how == "search":
        print(f"(found by searching {Path.cwd()}; it will be recorded at the "
              f"next park)", file=sys.stderr)
    elif how == "unstamped":
        print("(no park stamp — built by jsa_handoff.py, or not a jsa-park "
              "note; check what it is before trusting it)", file=sys.stderr)


def cmd_park(args):
    current = find_current_session()
    us = usages(current)
    if not us:
        sys.exit(f"jsa_meter: no usage records in {current.name}")
    _, last, _ = us[-1]
    stamp = {
        "session": current.stem,
        "parked_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "context_tokens": ctx(last),
        "requests": len(us),
    }
    model = last_model(us)
    if model:
        stamp["model"] = model
    line = f"<!-- jsa-park-meter: {json.dumps(stamp)} -->"
    print(f"parked session : {current.stem[:8]}  "
          f"context {fmt(stamp['context_tokens'])} tokens after {len(us)} requests"
          + (f"  [{model}]" if model else ""))
    if args.write:
        note = Path(args.resume_file)
        if not note.exists():
            sys.exit(f"jsa_meter: {note} not found — write RESUME.md first, then stamp it")
        text = STAMP_RE.sub("", note.read_text(encoding="utf-8")).rstrip("\n")
        note.write_text(text + "\n\n" + line + "\n", encoding="utf-8")
        print(f"stamp written to {note.resolve()}")
        # Record the location, so a fresh session started in the launch
        # directory finds a note that was written in a subfolder.
        try:
            reg = load_registry()
            reg[current.parent.name] = {"note": str(note.resolve()),
                                        "session": current.stem,
                                        "parked_at": stamp["parked_at"]}
            save_registry(reg)
            print(f"location recorded in {REGISTRY}")
        except OSError as e:
            print(f"jsa_meter: could not record the location ({e}); "
                  f"jsa-resume will fall back to searching", file=sys.stderr)
    else:
        print("append this line to RESUME.md (or re-run with --write):")
        print(line)


def cmd_resume(args):
    current = find_current_session()
    if args.resume_file:
        note = Path(args.resume_file)
    else:
        note, _ = locate_note(current.parent, Path.cwd())
        if note is None:
            sys.exit(f"jsa_meter: no {NOTE_NAME} parked from this launch directory")
    if not note.exists():
        sys.exit(f"jsa_meter: {note} not found")
    stamp = read_stamp(note)
    if not stamp:
        print("jsa_meter: no park stamp in the note — nothing to compare. "
              "(Notes built by jsa_handoff.py, or parked before the meter "
              "existed, have no stamp.)")
        return
    if current.stem == stamp["session"]:
        print("jsa_meter: this IS the parked session — the meter only makes "
              "sense from a fresh session. Nothing to compare.")
        return
    us = usages(current)
    if not us:
        sys.exit(f"jsa_meter: no usage records yet in {current.name}")
    _, first, _ = us[0]
    c_old = stamp["context_tokens"]
    c_new = ctx(first)
    saved = c_old - c_new

    parked_at = datetime.datetime.fromisoformat(stamp["parked_at"])
    gap = datetime.datetime.now().astimezone() - parked_at
    gap_h = gap.total_seconds() / 3600

    # The estimate is about what you pay from here on, so the read weight
    # comes from the model this fresh session is using.
    model = last_model(us)
    if args.cache_read_rate is not None:
        read, rate_note = args.cache_read_rate, "override"
    else:
        read, recognised = read_rate(model)
        if recognised:
            rate_note = f"for {model}"
        elif model:
            rate_note = f"assumed; {model} not in the rate table"
        else:
            rate_note = "assumed; model unknown"
    write = args.cache_write_rate if args.cache_write_rate is not None else WRITE_1H

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
    print(f"estimated savings (1h-cache write x{write}, "
          f"cache read x{read} {rate_note}):")
    print(f"  per cold restart after a 1h+ break : "
          f"~{fmt(saved * write)} input-token eq avoided")
    print(f"  per message from now on            : "
          f"~{fmt(saved * read)} input-token eq lighter "
          f"(vs. continuing the old session)")
    parked_model = stamp.get("model")
    if parked_model and model and parked_model != model:
        print(f"note: the parked session ran on {parked_model} and this one "
              f"on {model}. The rate above is this session's, since that is "
              f"what the messages from here on will bill at.")
    if gap_h < 1.0:
        print(f"note: the break was only {gap_h:.1f} h, so the old cache was "
              f"likely still warm — this restart itself was not the saving. "
              f"The numbers above apply to every 1h+ break avoided from here on.")


def rate_arg(value):
    try:
        f = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{value!r} is not a number")
    if f <= 0:
        raise argparse.ArgumentTypeError("rate weights must be positive")
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("park", help="stamp RESUME.md with this session's final context size")
    p.add_argument("--resume-file", default="RESUME.md")
    p.add_argument("--write", action="store_true",
                   help="append the stamp to the note (default: print only)")
    p.set_defaults(func=cmd_park)
    loc = sub.add_parser("locate", help="print the path of the note parked "
                                        "from this launch directory")
    loc.set_defaults(func=cmd_locate)
    r = sub.add_parser("resume", help="print the savings report for a fresh session")
    r.add_argument("--resume-file", default=None,
                   help="the note to compare against (default: as `locate`)")
    r.add_argument("--cache-read-rate", type=rate_arg, default=None, metavar="X",
                   help="cache-read weight vs base input (default: per model, "
                        f"{READ_DEFAULT} if unknown)")
    r.add_argument("--cache-write-rate", type=rate_arg, default=None, metavar="X",
                   help=f"cache-write weight vs base input (default: {WRITE_1H}, "
                        "the 1h TTL rate)")
    r.set_defaults(func=cmd_resume)
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
