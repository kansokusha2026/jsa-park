---
name: jsa-park
description: Park a heavy Claude Code session before a long break, so it can be resumed in a fresh session for a fraction of the tokens. Use when the user says they are stepping away for a while, going to bed, stopping for today, 離席します, 今日はここまで, or explicitly invokes /jsa-park. Writes a RESUME.md handoff note with the judgment fields drafted from the live conversation.
---

# jsa-park — park the session before you walk away

Part of jsa-park (https://github.com/kansokusha2026/jsa-park), a companion
to the JSA measurement scripts (https://github.com/kansokusha2026/jsa).

The CLI sibling `jsa_handoff.py` builds the same note *after the fact*, from
logs — and its judgment fields stay blank, because logs record operations,
not decisions. You are running *inside* the live session: the decisions are
still in context, so you can draft those fields too. That is this skill's
entire reason to exist. Use this skill while the session is alive; use the
CLI when the session is already gone (usage limit, crash, closed window).

Respond, and write RESUME.md, in the language of the conversation
(Japanese conversation → Japanese note).

## Step 0 — break-even check

First determine (from what the user said, or by asking once): will they be
back within about 1 hour?

- **Back within ~1 hour** → parking is usually not worth it. The prompt
  cache typically survives short breaks, and continuing the same session
  costs mostly cheap cache reads. Say so, and stop — unless the user
  explicitly wants to park anyway.
- **Longer than ~1 hour, overnight, unknown, or a usage-limit lockout** →
  proceed. After a long gap the cache has expired, and the next message in
  this session would re-register the whole conversation (hundreds of
  thousands of tokens in heavy sessions).

## Step 1 — draft the note

Use this two-part structure — the same field layout as `jsa_handoff.py`,
so the two tools' output stays interchangeable.

**Part 1 — the operations** (you know these directly from the session):

- Source line: parked from this live session, with date and time
- Where the work stands: tasks done / in progress / not started
- Files edited in this session
- The state at parking time (what was just finished, what was mid-flight)

**Part 2 — the judgments** (the part the CLI can never fill):

- **Goal / 目的** — what this work ultimately achieves. One sentence.
- **Decided / 決まったこと** — ONLY items the user explicitly approved.
  For each item, add a short pointer to the user's approving words.
  If you cannot point to an approval, the item does not belong here.
- **Proposed, not approved / 保留中の提案** — everything you proposed that
  the user has not (yet) approved. When in doubt, put it here, never in
  Decided.
- **Next action / 次にやること** — ONE concrete step, not "continue".

Optional fields — include only when the conversation actually contains
them: Rejected alternatives (with the reason each was rejected) /
検討して採らなかった案, Changed premises / 前提が変わったこと,
Unresolved flags / 未解決の指摘・違和感, Files not to touch / 触らないファイル.

End the file with:

- How to resume: start a **fresh** session and read this file first,
  confirming its contents before any work. (With `jsa-resume` installed,
  saying "再開します" / "resume" is enough.)
- Security note: the note contains file paths and work details, which can
  include credentials or internal URLs — check the contents before sharing.

## Step 2 — confirm the one thing that matters

Show the draft (at minimum the four core fields) and ask the user to check
exactly one thing: **is anything under "Decided" actually still just a
proposal?** Move items per their answer. This mix-up is the main way a
resumed session goes wrong, and it is the reason the two fields exist.

## Step 3 — write, with backup, and stamp for the meter

Write the note to `RESUME.md` in the project root. If one already exists,
rename it to `RESUME.md.bak` first (one generation kept, same convention
as the CLI).

Then stamp the note so the savings can be measured at resume time:

```bash
python3 "<this skill's base directory>/jsa_meter.py" park --write
```

The stamp records this session's final context size (read locally from
`~/.claude/projects/`; nothing leaves the machine). At resume time,
`jsa-resume` compares it against the fresh session's cold start and shows
the user what the park saved, in tokens. If the script fails, say so and
continue — the note itself is the deliverable.

## Step 4 — release the session

Tell the user, plainly:

- This session can now be closed. Continuing to type here after a long
  break would rewrite the whole conversation.
- To resume: open a fresh session in this folder and say
  "再開します" / "resume" (with `jsa-resume` installed), or paste:
  *"Read RESUME.md and confirm its contents first. Do not start working yet."*
- Don't commit `RESUME.md` by accident — keep it (and `RESUME.md.bak`)
  in `.gitignore`.

## What this skill deliberately does not do

- Keep the cache warm with periodic pings — every ping is billed, so
  nothing is saved.
- Detect your absence automatically — invoke it *before* you leave.
- Close the session for you.
