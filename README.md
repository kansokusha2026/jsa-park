# jsa-park — park a heavy Claude Code session before you walk away

Leave a heavy Claude Code session alone for an hour or more and its prompt
cache expires. The next message you type re-registers the whole
conversation into cache — in heavy sessions, hundreds of thousands of
tokens for a single turn.

**jsa-park is a pair of Claude Code skills that turn a long break into a
cheap restart:** park the session before you leave, resume in a fresh one
for a fraction of the tokens.

| Skill | When | What it does |
|---|---|---|
| **`jsa-park`** | Before the break | Writes a `RESUME.md` handoff note — including the judgment fields (*Decided*, *Proposed but not approved*, *Next action*) drafted from the live conversation |
| **`jsa-resume`** | After the break | In a fresh session, just say "resume". Reads `RESUME.md`, reports what was decided versus merely proposed, shows **what the park saved, in tokens**, and waits for your go-ahead |

[日本語 README](README.ja.md)

## Install

```bash
git clone https://github.com/kansokusha2026/jsa-park.git
cd jsa-park
mkdir -p ~/.claude/skills && cp -r skills/jsa-park skills/jsa-resume ~/.claude/skills/
```

New sessions pick the skills up automatically. To uninstall, delete the
two folders from `~/.claude/skills/`.

## How `jsa-park` works

Invoke it with `/jsa-park`, or just tell Claude you're stepping away.

1. **Break-even check.** Back within about an hour? Then the cache usually
   survives and parking isn't worth it — the skill says so and stops.
   Longer, overnight, or a usage-limit lockout → proceed.
2. **Draft.** It writes a two-part note: the operations (tasks, edited
   files, current state) and the judgments — *Decided* holds only what you
   explicitly approved, each item with a pointer to your approving words;
   everything else lands in *Proposed, not approved*.
3. **Confirm one thing.** You check a single question: is anything under
   *Decided* actually still just a proposal?
4. **Release.** The note is saved (an existing `RESUME.md` is kept as
   `RESUME.md.bak`), and the session can be closed.

## How `jsa-resume` works

Open a fresh session in the same folder and say **"resume"** (or
`/jsa-resume`). The skill finds `RESUME.md`, checks its date, reports
Goal / Decided / Proposed / Next action, shows the savings meter — and
does **not** start working until you say go. Items under *Proposed, not
approved* are never treated as settled. Resuming this way costs a few
thousand tokens instead of re-registering the whole previous conversation.

Because every resumed session starts from the trigger phrase, its title
tends to end up as just "Resume". Where session-management tools exist
(the Claude Code desktop app), the skill also renames the parked
predecessor to inherit the original title with a sequence number
("X" → "X(2)" → "X(3)") — one step behind, since a session cannot rename
itself. In a plain CLI session this is skipped silently.

## The savings meter

A saving you can't see is a habit you won't keep. So the skills measure
it, on every cycle:

- `jsa-park` stamps `RESUME.md` with the parked session's final context
  size, read from your local transcripts in `~/.claude/projects/`
  (standard library only, nothing leaves your machine).
- `jsa-resume` compares that stamp against the fresh session's actual
  cold start and reports the difference — every time you resume.

A real example, from the session this feature was built in:

```
=== jsa-park savings meter ===
parked session : 6297ec16  context 160,011 tokens after 77 requests (2026-08-12 08:47)
fresh session  : 96bd6731  cold start registered 78,680 tokens
context shed   : 81,331 tokens (-51%) — conversation history replaced by the handoff note
estimated savings (rate weights: 1h-cache write x2.0, cache read x0.1):
  per cold restart after a 1h+ break : ~162,662 input-token eq avoided
  per message from now on            : ~8,133 input-token eq lighter (vs. continuing the old session)
```

Here ~81k tokens of conversation history were replaced by a ~1.5k-token
handoff note; what remains is mostly the fixed per-session cost (system
prompt, tools, project instructions), which every session pays anyway.
The estimates use model-agnostic rate weights — a 1h-cache write bills at
roughly 2x the base input rate, a cache read at roughly 0.1x — so no
prices are assumed and the numbers hold for any Claude model.

## Relation to JSA

[JSA](https://github.com/kansokusha2026/jsa) is the measurement side:
three standalone Python scripts that read your local Claude Code logs.

- **Measure first.** Run JSA's `jsa_gaps.py` to see whether resumption
  cost is actually hitting you. If its verdict says the handoff workflow
  is worth adopting, these skills automate it.
- **Same note, two directions.** JSA's `jsa_handoff.py` builds `RESUME.md`
  from logs *after* a session is gone — its judgment fields stay blank,
  because logs record operations, not decisions. The `jsa-park` skill runs
  *inside* the live session, where the decisions are still in context, so
  it can draft those fields too. In one line: **the CLI recovers
  operations from a dead session; the skill writes down judgments from a
  live one.**
- Use `jsa-park` when you can see the break coming. Use `jsa_handoff.py`
  when the session is already gone (usage limit, crash, closed window).
  The two produce interchangeable notes: `jsa-resume` reads either.

## Notes

- Neither skill keeps the cache warm. Pinging a session on a timer is
  billed like any other message and saves nothing — the saving comes from
  *not carrying the old conversation into the new session*.
- The skills add their trigger descriptions to every session's fixed cost.
  It's small (well under a thousand tokens for the pair), but if you use
  them rarely, weigh it.
- `RESUME.md` lands in your project root and is **easy to commit by
  accident**. Add `RESUME.md` and `RESUME.md.bak` to `.gitignore`.
- The note contains work details and file paths, which can include
  credentials or internal URLs. Check the contents before sharing.
- Not a replacement for `/compact`, `/clear`, or `/resume`. Try the
  built-ins too, and pick whatever works best for you.

## License

MIT. See [LICENSE](LICENSE).

## Background

Like JSA, the core idea comes from the Japanese-language book
*あのプロジェクトは、なぜ止められなかったのか* ("Why couldn't anyone stop
that project?", Kansokusha, 2026) and the Judgment Structure Audit it
proposes: decisions that are never written down cannot be handed off.

Kansokusha is on X: [@kansokusha2026](https://x.com/kansokusha2026).
