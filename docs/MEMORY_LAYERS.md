---
title: MEMORY_LAYERS.md
description: Integrator guide. Lifetime-sorted memory, Kaskade cascade, and optional agent patterns (approval, cadence, propose-only reports, research triage).
created: 2026-10-26
updated: 2026-11-03
---

# Memory layers

This document says how to wire Kaskade. It stays short and stays true of this repo. The full agent is [MEMORY_SYSTEM_BLUEPRINT.md](MEMORY_SYSTEM_BLUEPRINT.md). Index: [README.md](README.md).

Sort blocks by lifetime, not by topic. Topic-sorted stores age together. Lifetime-sorted stores keep the stable part cacheable.

Spark and Bridge Rise: [GNOSTIC_SPARK.md](GNOSTIC_SPARK.md), [BRIDGE_RISE.md](BRIDGE_RISE.md).

## Three lifetimes

| Layer | How often it changes | Job |
|-------|----------------------|-----|
| Doctrine | almost never | Read. Do not rewrite on a whim. |
| Reference | weekly | Lookup. Cue-gated. |
| Working memory | hourly | Overwrite. Do not curate. |

Put text that changes every hour in its own section. Keep doctrine and identity in a prompt cache key that does not include that section. If you mix them, every heartbeat busts the whole cache.

Kaskade holds the archival cascade and the graph. Named core blocks still live in your agent, or in Postgres rows you treat as core. This repo is not a chat product.

```text
your agent
  ├─ core blocks in the prompt (doctrine, person, scratchpad, days)
  ├─ Kaskade archival  →  day → week → month
  ├─ Kaskade graph     →  search, Spark, Bridge Rise
  ├─ optional cadence    (core every 10, archive every 50)
  ├─ optional night report   (read gates and tickets, write a report)
  └─ optional approval store  (not memory, not in this repo)
```

Core is what the agent carries. Archive is what it has to fetch. Spark may inject one rare line. Rise may inject one or two lines only when Door-B has two independent sharp signals. P = 5 never appears in a spontaneous Spark.

## Starter blocks (in the agent)

Start with five to seven. Split a block only when it already does two jobs.

| Block | Lifetime | What belongs |
|-------|----------|----------------|
| `person` | doctrine / slow reference | The human in front of you. Nicknames, limits, how they talk, corrections. Not a biography. |
| `constitution` | doctrine | Non-negotiable values, stop words, who may do what. |
| `errors` | reference | Number, date, what happened, what to do instead. The list records the mistake. A check in your agent prevents the next one. |
| `scratchpad` | working | Open threads. Hard size cap. Overwrite, do not append. |
| `days` | working → archive | Recent prose with timestamps. Roll into Kaskade archival on a schedule, then restart the hot block. |
| `person_packs` | reference, cue-gated | One pack per important person. Load only when that person is in context. |
| `feed` | read-only | Host-filled facts the agent must not overwrite. |

Kaskade maps most cleanly to `days` rolling into archival, and to cue-gated reference (theme, person, Spark, Rise). Keep `constitution` and `errors` in the prompt unless you store copies as archival on purpose.

## Scratchpad rules

In:

- Open threads, each with an owner and a next action
- What is blocked, and on whom
- What was delivered, one line per item

Out:

- Narrative → `days`, then Kaskade archival
- Feelings → their own block, or nowhere
- Dated tasks → a task system, not memory
- Quotes and papers → archive

Use timestamps, short lines, and an `Open:` list at the bottom. Status, not narrative.

Two rules:

1. Overwrite. Do not append. An appending scratchpad becomes a second `days`. Then both grow without a bound.
2. Keep a hard size cap. A full block is an emergency. The usual failure is to park the new fact in a second place and keep two incomplete copies.

## Refine, then freeze

```text
scratchpad  →  days  →  Kaskade archival  →  doctrine
 hourly        daily      weekly / EOD         after it repeats
```

A thread that shows up three times is no longer a note. It is a rule. Example: "run the tool, then say done" starts as an open item, becomes a day line, then an `errors` row, then one line in `constitution`. After that the agent should not rediscover it from chat.

Kaskade's vertical cascade is the middle of that path: `rolling_days` → `weekly_summary` → `monthly_summary` → `yearly_essence`. End-of-day reconcile can call a coding-agent hook (`KASKADE_EOD_AGENT_PROVIDER`).

## Visibility

Not every block belongs in every turn.

| Always | On cue | Stay out |
|--------|--------|----------|
| Doctrine, identity | Person packs, hobby notes, project notes | Raw feed, old history, P = 5 except on purpose |

Kaskade's prompt gate is `GET /api/memory/core/filter` plus [`config/core_memory_gates.yaml`](../config/core_memory_gates.yaml). Default omit. Include when a channel, keyword, or message type matches. Load the packs that match this turn. Do not load every reference block every time.

## What enters the prompt from Kaskade

| Path | When | Limit |
|------|------|--------|
| Search / Gnostic traverse | The agent asks, or your loop searches | You choose the slice |
| Spark | Rare, cooldown, two cue types, P < 5 | One line |
| Bridge Rise | Door-B: two of fragment, archival tag, topic weather | One or two lines |
| Cascade day bundle | The UI or an EOD job | Themes and archivals for that day |

Do not inject the whole archive. Do not treat a Spark as a citation. Your own note is a hypothesis until you verify it.

## Writes

| Action | Typical rule |
|--------|----------------|
| Edit text in an existing core block | Direct. Watch for drift. |
| Create, delete, or lift a core block into archive | Ask a human. Structure changes are not the same as content edits. |
| `POST /api/cascade/archival` | Goes through ERIP parse, significance gate, maintainer queue |
| High P and no theme | Deferred to end of day when `HIGH_PRIVACY_THRESHOLD` applies |

Kaskade does not ship the approval queue. If you need a human before delete, put that in your agent. Spark still refuses P = 5.

## Patterns your agent can add

These patterns help a full agent. They are not a second product inside this repo. Wire them beside Kaskade if you want them. The text marks a hook when this repo already has one.

### Approval is not memory

Keep allow/deny in its own store. Wiping approvals must not wipe archival rows.

The agent may edit text in a block that already exists. Create, delete, or lift a block out of core almost always needs a human.

| Action | Typical tier |
|--------|----------------|
| Read, status | silent |
| Insert/replace on an existing block | auto-allow, then a drift watch (no silent rollback) |
| New block, delete block, archive a core block | ask |
| Destroy a database, change credentials, force-push the default branch | auto-deny, no override |
| Spawn agents, bulk change, spend | escalate |

Default when no rule matches: ask. An allowlist entry is one pair of agent and action. A child agent inherits neither an approval nor an allowlist row.

Kaskade: significance gate + maintainer queue on archival insert. Not a chat approval UI.

### Cadence, not a second person

A background pass of the same agent. Give it its own id if you want isolation. Writes still land in the main agent's blocks.

| Tick | Interval | Effect |
|------|----------|--------|
| Count | every message | counter only |
| Core | every 10th | narrow edits to existing core blocks |
| Archive | every 50th, user text, not a heartbeat or task | at most a few new archival rows |

In this repo, `kaskade/learning/loop.py` fires `core_loop` every 10 messages and `archival_mini_loop` every 50 when content is longer than 80 characters. It does not run an LLM editor. Your agent supplies the model and the tool cap. Keep the cap small, about 4 calls.

Do not let that pass rewrite identity, constitution, or a full `rolling_days`. Facts need dates. Do not write "today" into text that will still be there next month.

### Propose is not apply

A night worker may read gates, the last day's commits, and the open ticket list. It writes a report. It does not merge, push, restart a process, or edit product code. Block those actions in the runtime. A line in the prompt is not enough.

A green gate on a short diff is not a clean tree. If the ticket list is not empty, the first line of the report says so. Do not write "nothing red" while diagnoses or pending fix cards are still open.

A later pass may read large or frequently edited files. The night report only points at them. It must not claim a full-tree audit.

Kaskade does not run this worker. `kaskade/learning/loop.py` only counts. The end-of-day hook can call your agent. Neither of those is a license to apply a report.

### Research triage

External papers and weekly notes are not memory rows until you store them. Bucket first.

| Bucket | Meaning |
|--------|---------|
| `port_now` | Clear fit. Ticket-ready. Name the module. |
| `research_bridge` | Worth a short note. Not hot-path yet. |
| `watch` | Stay on the radar. No action this cycle. |
| `noise` | Skip. Say why in one line. |

Do not invent a paper claim without a source you can point to. A draft note is not a port. Do not re-propose the same bridge on the next cycle.

Kaskade archival is for days you chose to keep. A triage draft is an agent file. If a fact should survive, a human step writes `POST /api/cascade/archival` on purpose, with dates and an ERIP line.

### Tasks are intention, not a memory row

A task is when, where, and with which tools. Until it fires it is a card. When it fires it is a message of type `task`. Preload the sources before the model turn so the agent does not search for what you already fetched.

Do not auto-archive a task turn. Heartbeat and task should not trigger the archive cadence. If it should stay, a step writes `POST /api/cascade/archival` on purpose.

### Pulse is a short chain, not a card

Beside the board: a few pings after a real reply, or a clock interval. One agent, one pulse in flight. A human turn does not stack a second one. Not approval-gated. Not a substitute for `days`.

Not in this repo.

### Live feed vs stored journal

Two sources, one rule. While a short live line is on this turn, keep the stored journal block out of the prompt. The block is the last known view for when the device is gone. Sync into the block can keep running.

That is the `feed` block from the starter list: the agent must not overwrite the host's perception. A diary in the agent's voice is ordinary core memory. Captions are not.

Not in this repo. Time Circle shows archival days, not a camera.

### One thread, sessions as stretches of time

One timeline per agent. A channel is origin metadata, not a second conversation. After a pause of about 10 minutes, the next line can mark "since your last chat" and bring a thin reminder from that same place. The thread does not split.

Leave private sessions and noisy side streams out of the default window. If the merge fails, fall back to this channel only.

Kaskade stores archival by `day_id` and theme, not chat transcripts. Keep the raw message store in your agent. The prompt gets a slice, not the table.

### Stable vs volatile in the prompt cache

Both kinds still enter the prompt every time. Only the cache treats them differently.

| Stable (cacheable) | Volatile |
|--------------------|----------|
| Doctrine, identity, constitution | `days`, scratchpad, heartbeat |

If volatile text sits in the same cache key as doctrine, every scratchpad overwrite busts the whole prompt.

## Sizes (starting points)

| Kind | Size | Write rate |
|------|------|------------|
| Doctrine | 3 to 10k characters | months |
| Identity | 10 to 20k | almost never |
| Reference | 5 to 20k | weekly |
| Working memory | 2k hot / 15k days | hourly |

A block at 100% cannot take a new fact. Archive the oldest day before you cut. Saving is cheap. Reconstructing is not.

## Operating rules

- View the stored bytes, then replace. Text from a rendered window does not always match.
- One structural edit per turn. Otherwise you cannot tell which write did what.
- Deduplicate weekly. Without that, working memory piles up unused copies.
- Facts need dates. Words like "today" and "recently" rot. Kaskade archival rows carry `episode_date` and `day_id`.

## What this repo is not

- Not an LLM ranker on Spark or Rise
- Not a vector-only store
- Not a hosted chat, bot, approval UI, or device journal
- Not a dump of private conversations. Demo people are `alex`, `sam`, and `agent`

The patterns above are how a full agent stays honest next to Kaskade. Wire search, Spark simulate, and Rise simulate from [the README API list](../README.md#api). Keep doctrine in the agent. Let Kaskade remember the days.
