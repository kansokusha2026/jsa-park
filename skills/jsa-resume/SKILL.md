---
name: jsa-resume
description: Resume parked work from a RESUME.md handoff note. Use when the user starts a session with 再開します, 続きから, "resume", "let's pick up where we left off", or invokes /jsa-resume. Reads RESUME.md, reports Goal / Decided / Proposed / Next action, and waits for a go-ahead before doing any work.
---

# jsa-resume — pick the work back up, carefully

Part of jsa-park (https://github.com/kansokusha2026/jsa-park).
Counterpart of the `jsa-park` skill. Respond in the language of the
conversation.

1. **Find the note.** Look for `RESUME.md` in the current project root.
   If it is missing, say so and suggest building one from the last
   session's log:
   `python3 /path/to/jsa/jsa_handoff.py -o RESUME.md`
   — then stop.

2. **Read it, check its date.** Note the last-updated stamp in the file.
   If it looks stale relative to what the user is describing, say so
   before anything else — resuming from an old note silently rewinds
   decisions.

3. **Report back, briefly:** Goal, Decided, Proposed-not-approved, Next
   action. Treat everything under "Proposed, not approved" strictly as
   unapproved — never act on those items as if they were settled. That
   separation is the entire point of the note.

4. **Show the savings meter — every time.** Run:

   ```bash
   python3 "<this skill's base directory>/../jsa-park/jsa_meter.py" resume
   ```

   (the script ships in the sibling `jsa-park` skill folder). Relay its
   report in the conversation's language: old context vs. fresh start,
   percentage shed, and the per-restart / per-message estimates. Seeing
   the number each time is what makes the parking habit stick. If the
   script, the note's stamp, or the sibling folder is missing, skip this
   step silently — never block the resume on it.

5. **Tidy the session lineage — only where session tools exist.** A
   resumed session starts from the trigger phrase, so the previous
   session is often left titled just "再開" / "Resume". If
   session-management tools are available (a session list plus a
   rename-session tool, as in the Claude Code desktop app): find the
   most recent *other* session in the same project directory whose
   title is still such a generic resume phrase — that is the parked
   predecessor — and rename it to inherit the lineage title: the most
   recent non-generic title in the same directory, with a sequence
   number appended or incremented ("X" → "X(2)" → "X(3)"). The current
   session cannot rename itself; if the user wants this one renamed
   too, point them to the session-list UI. In a plain CLI session these
   tools don't exist — skip this step silently, never mention it.

6. **Confirm only — do not start.** Ask: "Is this current? Shall I start
   with [the next action]?" Begin working only after the user says go.

7. **Do not re-read the previous session's full log.** The note *is* the
   handoff; pulling the old conversation back in defeats the purpose.
   If more context is needed, ask the user to point at specific files.
