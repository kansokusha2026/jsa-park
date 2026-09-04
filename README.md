# jsa-park — skills that cut the token cost of long breaks and restarts in Claude Code

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

## What carries over, and what does not

An LLM has no memory across sessions. Every response is generated from
the token sequence sent with that one request — the system prompt plus
the full conversation history. The old session could answer "in
context" only because that entire history was sent along every time.

The handoff note is a lossy compression of that history. It keeps
conclusions, open questions, the current position, and the next step;
it discards the reasoning that led there, the contents of files that
were read, and the failed attempts. This works in practice because most
facts are externalized in files — code, notes, Git history — which the
fresh session can re-read on demand.

What lives in neither files nor logs is the judgment layer: logs record
operations, not which proposals were approved and which were rejected.
That is why the note's fill-in fields separate "Decided" from
"Proposed, not approved". A judgment that was never written down does
not carry over, and typically resurfaces as the new session
re-proposing an idea the old one had already rejected. This is also why
`jsa-resume` waits for your go-ahead before working: so you can catch
what was lost before it turns into rework.

## Compared with the built-in resume and compaction

Claude Code has its own ways to shorten a long history: `/compact`
replaces the conversation with a summary, and on a Pro or Max plan,
resuming a large session after a long break offers to continue from a
summary so later requests don't carry the full history. Reach for those
first if they fit. This project isn't trying to replace them.

Two differences are worth knowing before you choose.

### Summarizing costs the most at the moment you need it

Building a summary means reading the whole history. While the cache is
warm that's cheap, but after a break longer than the cache lifetime
there's no cache left to read, so the summarization request reprocesses
the whole history as uncached input. That's exactly when you reach for it:
coming back to an old session. The conversation is long because you were
away, and it costs the most to summarize *because* you were away.
`jsa-park` moves that work to *before* the break, while the cache is still
warm and the conversation is still in context.

### A generated summary keeps what you did, not what you decided

It's built from the transcript, and a transcript records operations. It
shows what was tried, edited and run. It doesn't mark which proposals you
approved and which you turned down, because a rejected plan leaves the
same trace as an accepted one: you discussed it.

Lose that distinction and the next session confidently re-proposes
something you already considered and rejected, so you explain it and turn
it down a second time. Of everything a handoff drops, this is the most
expensive.

`jsa-park` keeps *Decided* and *Proposed, not approved* as separate fields
and asks you to check exactly one question before saving: is anything
under *Decided* actually still just a proposal? An automatic summary has
no such gate.

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

- After parking, don't type anything into the **old** session — not even
  "I'm back". If more than an hour has passed, that one message
  re-registers the whole conversation, which is exactly the cost parking
  was meant to avoid. The comeback signal ("resume") belongs in a fresh
  session. If you did send something by accident, still move to a fresh
  session for the rest of the work — every later message will be lighter.
- Neither skill keeps the cache warm. Keeping it alive on a timer does
  work: a keep-alive re-send bills at the cache-read rate rather than the
  full input rate, so on models with cheap cache reads it can undercut a
  cold restart for a fairly long break. It never undercuts parking,
  though. Pinging pays, over and over, to *preserve* the conversation that
  parking simply stops carrying, and the bill grows with every hour you
  stay away. The saving here comes from *not carrying the old conversation
  into the new session*.
- The skills add their trigger descriptions to every session's fixed cost.
  It's small (well under a thousand tokens for the pair), but if you use
  them rarely, weigh it.
- `RESUME.md` lands in your project root and is **easy to commit by
  accident**. Add `RESUME.md` and `RESUME.md.bak` to `.gitignore`.
- There is one `RESUME.md` per project folder. Parking different
  projects in parallel is fine — but parking the *same* folder twice
  moves the previous note to `RESUME.md.bak`, and a third park discards
  it. Only one backup generation is kept. To resume the older note,
  restore `RESUME.md.bak` to `RESUME.md` before saying "resume".
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
