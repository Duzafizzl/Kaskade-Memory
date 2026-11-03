---
title: MEMORY_SYSTEM_BLUEPRINT.md
description: Full agent memory loop. Core, archive, history, tasks, graph, auto-recall, live feed, and a separate approval database.
created: 2026-10-24
updated: 2026-11-03
---

# Memory system blueprint

This document describes the full agent loop: core, archive, history, tasks, live feed, and approval. It does not specify every file in `kaskade/`. The Kaskade map is [MEMORY_LAYERS.md](MEMORY_LAYERS.md). Index: [README.md](README.md).

Written 2026-10-26. It covers what sits in the prompt, what is fetched, what a task is, and what is not memory.

Kaskade in this repo is the archival cascade, the graph, Spark, Bridge Rise, prompt gates, and the 10/50 cadence counters. The other sections are the agent you attach.

An agent has four kinds of memory, and an approval database that is separate from all of them.

- **Core memory** is in the prompt on every turn, unless a filter drops that block for this turn. Each block has a name, a description, and a character limit.
- **History** is one long thread, not a store per channel. A session is only a stretch of time. After a pause, the last messages from that same channel join as a reminder (section 10).
- **Archival memory** is searchable long-term storage. It enters the prompt only when something searches for it, or when auto-recall is set to inject.
- **Tasks** are the plan. A card says when something should happen. When it fires, the job arrives as a message, and with it the material that does not have to be searched for first (section 9).
- **Approval** is not memory. Requests, heartbeats, and "always allow" live in their own SQLite file. Postgres is touched only after an allow.

The full message store in Postgres stays raw material. The prompt gets the slice from section 10, plus whatever the filters and the trigger add.

---

## 1. Two databases

```text
one message
  │
  ├─ Postgres, table memories
  │     core     = named blocks, size-capped, usually in the prompt
  │     archival = searchable rows, not in the prompt until a search
  │
  ├─ Prompt filters (not a store)
  │     which core blocks actually join this turn
  │
  └─ SQLite data/approval.db
        heartbeats, events, approval queue, allowlist
        governance, not memory
```

### Postgres

| `memory_type` | Meaning | In the prompt? |
|---------------|---------|----------------|
| `core` | Named blocks. Character limit per block (`metadata.limit`, otherwise env `CORE_MEMORY_MAX_SIZE`, default 2000). | Yes, after the filters in section 4. Blocks with `hidden=true` are absent from the default list. |
| `archival` | Many rows with tags and metadata. Stored under the label `archival`. | No. Only via search (`archival_memory_search` or the retrieval index), or when a tool quotes a row. |

Spend lives in the Postgres table `costs`. The approval database reads it. It does not store it.

`read_only` on a core block blocks tool edits. A save in the UI and a version rollback can bypass that. There is no "agent A writes, agent B reads" permission. Each agent has its own rows (`agent_id`).

### SQLite, separate from Postgres

Switch `APPROVAL_DB_PATH`, otherwise the default SQLite file. WAL is on. One process writes.

Heartbeats are ephemeral. Approvals can be wiped without losing memories.

| Table | Contents |
|-------|----------|
| `agent_heartbeats` | last heartbeat per agent |
| `state_transitions` | status changes, append-only |
| `events` | ring buffer, last 50 events |
| `agent_overrides` | agents discovered automatically |
| `approval_requests` | chat approval: pending, allowed, denied |
| `approval_allowlist` | "always allow" for one agent and one action |
| `task_anchor_suppressions` | scheduled tasks a watchdog must not restore |

An approval does not write a memory. After an allow, the approval API runs the side effect (create, delete, or archive a block, or change who can see it). That side effect lands in Postgres.

---

## 2. Core and archive

| | Core | Archive |
|--|------|---------|
| Shape | a few blocks with name, description, and limit | many rows, tags, metadata |
| Size | hard character limit | no prompt budget |
| Visible | every turn, until a filter drops the block | only on search |
| Who writes during chat | the main agent, via memory tools | the main agent via `archival_memory_insert`, plus the learning agent on the archive cadence |
| Stability | medium. The learning agent may make narrow edits every 10 messages | high. Auto-save is rare and conditional |
| How it goes away | the block stays until someone clears it, replaces it, or (with approval) deletes or archives it | the row stays searchable. "Forgotten" means it is not placed in the prompt |

Core is what the agent carries on every reply. The archive is what it has to go and fetch.

### Writes, deletes, new blocks

Not every write weighs the same. The agent may write content into a block that already exists. Changing the structure (create, delete, lift out of core) almost always needs approval.

| Action | Approval? | After |
|--------|-----------|-------|
| `memory_insert`, `memory_replace`, `memory_rethink`, `core_memory_replace` on a block that already exists | No. Goes straight to Postgres. | A drift watch runs in the background. The write stays. |
| New block, `core_memory_block_create` | Yes, on by default (`CORE_MEMORY_CREATE_APPROVAL`). | The block exists only after an allow. |
| Delete a block, `core_memory_block_delete` | Always. This tool has no env switch that turns the queue off. | Gone only after an allow. |
| Lift a block into the archive, `core_memory_block_archive` | Yes, on by default (`CORE_MEMORY_ARCHIVE_APPROVAL`). | A copy goes to the archive. Core can be removed after that. |
| Delete a file, `delete_file` | Ask. |  |
| Destroy a database (`delete_database`, `drop_table`, `truncate_table`, `factory_reset`) | Auto-deny. No override. |  |
| Bulk delete, `bulk_delete` | Escalate. |  |
| Delete a scheduled task | Ask. It does not expire on its own. |  |

`persona` and `human` cannot be deleted. A copy can go to the archive. Removing them from core cannot.

#### Rules for a new block

All of these hold before Postgres sees a row:

1. The name is non-empty. One name, once. If it already exists, the answer is "already there, edit it", not a second create.
2. `description` is required: one or two sentences on what the block is for. Without it the error is `DESCRIPTION_REQUIRED`.
3. A character limit, otherwise `CORE_MEMORY_MAX_SIZE` (default 2000).
4. If the initial text names a calendar week, it has to match the date. Otherwise the write is rejected (`MEMORY_ISO_KW_MISMATCH`).
5. Who should see the block (channel, server, keyword) is on the same approval. Without an allow, none of that sticks.
6. The window is 10 minutes. Only an allowlist entry for that exact agent and `memory_block_create` may pass immediately.
7. `memory_insert` on a name that does not exist does not create the block quietly. Only `core_memory_block_create` does that.

Delete and archive also need a reason, at least 3 characters.

#### Drift watch after a write the agent made itself

Because the agent may edit existing blocks without approval, every such write starts a background job (`_schedule_core_tool_delta_enrichment`). It does not undo the write.

1. Optionally, an enrichment of the delta (tags, metadata on the block).
2. The drift daemon, on by default (`CORE_DRIFT_DAEMON_ENABLED`). It sees before, after, and the recent versions (default 10) and judges `stable`, `moderate_drift`, or `major_drift`, plus a short plain-language summary. If the score is high enough, a message goes to an operations log. The verdict is stored in `core_memory_enrichment_log`. No rollback.

Two other clocks, not the same job:

- Every 6 hours, and only if `rolling_days` actually changed: a delta summary into the archive (what changed, why it matters). Unchanged content is skipped.
- Weekly: the largest core blocks (default from 1200 characters, at most 6) are compared across recent versions. A chat summary only if `CORE_MEMORY_WEEKLY_DRIFT_SUMMARY` is on. The per-block ping is off for that run.

---

## 3. When something moves to the archive

Four paths. They are not the same thing.

### 3.1 Learning agent, slow cadence

The archive cadence is 50.

The counter lives in the process and returns to 0 after a restart. Chat and voice share it (`maintain_coherence`).

All of these must hold:

1. Message number divisible by 50 (50, 100, 150, …).
2. Role is `user`.
3. Text longer than 200 characters.
4. Message type is neither a periodic heartbeat nor a task.
5. If the optional quality gate is on, it must let the write through. Otherwise the log reason is `trc_blocked`.

Then `learning_agent.process_archival` runs. The reviewer sees a window of 50 messages by default, capped at 100 (`LEARNING_AGENT_ARCHIVAL_RECALL_LIMIT`). Heartbeats and tasks may **appear** in that window. They do not trigger the save. At most 2 new archive rows per run (`LEARNING_AGENT_ARCHIVAL_MAX_INSERTS_PER_TRIGGER`). Recent archive snippets sit beside the window so nothing is stored twice.

If the pass finds nothing worth storing, it may still write a row headed `[Auto-Save · Learning Agent]`. That does not happen if an `archival_memory_insert` already succeeded.

### 3.2 Daily log, before the limit breaks

Block name in the system: `rolling_days`.

At about **92%** of the character limit, or when the next write would exceed it, the **oldest day sections** move to the archive. Tags include `rolling_days`, `rolling_days_archive`, `rolling_days_pre_limit`, `day:YYYY-MM-DD`. Header: `Policy: rolling_days_pre_limit_maintenance`.

This is not a rewrite by the learning agent. A full rewrite of this block (`memory_rethink`) is forbidden for it (`ROLLING_DAYS_RETHINK_FORBIDDEN`). A full rewrite once collapsed the day log to a fraction of its size while the block stayed in every reply.

If the archive insert fails, the oldest day is still removed from the hot block (`reconciled_local_fallback`). The log line is `rolling_days_archive_failed`. A silent failure at the limit does not happen.

### 3.3 Delta every six hours

A delta summary writes the change in the daily log to the archive before a summary runs. That compresses. It is not a second memory.

### 3.4 Someone stores it on purpose

- The main agent, including over voice: `archival_memory_insert`. That is how a seen scene stays searchable.
- The tool `core_memory_block_archive` first opens an approval (`action_type=memory_block_archive`). Postgres is touched only after an allow. The core block can be deleted afterwards.

Every write, core and archive, checks calendar weeks. If the text names a week that does not match the date it names, the write is rejected (`MEMORY_ISO_KW_MISMATCH`). The default is reject, not a silent rewrite. The learning agent is not allowed to guess the week.

---

## 4. Which blocks join this turn

Entry point: `filter_core_blocks_for_turn`. This applies to the whole agent loop, not only to one chat channel.

Each step sees only what the previous step left. Hidden blocks (`hidden=true`) are already gone.

```text
all core blocks for this agent
  1. Channel routing            always visible, or only for a channel / word / message type
  2. Private session mode       one dedicated block, only while the mode is on
  3. Weekly and monthly rollup  only when display is explicitly on
  4. Topic block                only for a matching server or keyword (gate off by default)
  5. Narrow private mode        operational blocks and most tools drop out
  6. Companion device          vision block dropped while a live line carries what is seen
  7. Body                      vision block dropped while a live line carries what is seen
        │
        ▼
  MEMORY BLOCKS                 stable blocks, eligible for the prompt cache
  MEMORY VOLATILE               daily log and heartbeat scratchpad
```

### 4.1 Always included

`scope=all` means the block is not tied to one chat channel. A later filter can still drop it.

Typical blocks, inventory from **2026-08-15** (35 of them; the list may have grown): identity, boundaries, values, communication style, people, body and devices, cooking and project notes, the agent list, the daily log, the heartbeat scratchpad, both vision journals, a device diary, tool rules.

### 4.2 Only in the matching context

Metadata on the block: `prompt_scope`, `prompt_targets`, `prompt_keywords`, `prompt_include_message_types`.

The block is included when **one** of these is true:

- A channel, server, member, or direct message matches a stored target.
- A keyword appears in the user message (under 6 characters: whole word; 6 or more, or with `*`: word prefix).
- The message type is on the include list (for example heartbeat or task).
- The block is system-managed and the rule says it should come along now.

Examples from the snapshot: a science block, a project-specific block, a scoreboard, recent code commits, another channel-bound block.

Changing who can see a block (agent or UI) goes through the approval queue (`action_type=core_memory_routing`). Env `CORE_MEMORY_ROUTING_APPROVAL` defaults to on. Without an allow, the old rule stays.

### 4.3 Private session mode

A switch limits what a private conversation puts in the prompt.

| State | Prompt |
|-------|--------|
| Mode on | One block that exists only for this mode may be included. |
| Mode off, or the status check fails | That block is omitted. |
| Narrower variant on | Everyday and operational blocks drop out as well. The tool list shrinks to memory, search, voice, and camera, plus a short allowlist. |

### 4.4 Weekly and monthly summaries

`weekly_summary` and `monthly_summary` are built in Postgres even when nobody sees them in the prompt. Showing and building are two switches.

In the prompt only when:

- `CORE_MEMORY_PROMPT_INCLUDE_ROLLUP_SUMMARIES=1`, or
- `UNIFIED_RECALL_MODE=inject`

Without those env vars the default is `UNIFIED_RECALL_MODE=shadow`: built, not sent.

`monthly_essence` was hidden in the snapshot, so it is missing from the default list.

### 4.5 A block for one topic

One project-specific block has its own gate. The gate is **off** by default.

When it is on, the block is included only if the server id is allowed, the server name contains a configured string, or keywords appear in the message. If there is no context at all (no server, no message), the block stays in, so bare API calls do not run empty.

### 4.6 Stable and volatile

`rolling_days` and `heartbeat_scratchpad` sit under `MEMORY VOLATILE`, along with labels from `PROMPT_CACHE_EPHEMERAL_LABELS` or the metadata flag `prompt_cache_volatile`. They are still in the prompt every time. Only the cache treats them as the part that changes often. The rest may be cached.

### 4.7 What the learning agent must not change

- the identity block and the frozen protocol block
- any block with `read_only` or `learning_agent_read_only` (in the snapshot, also recent commits)
- a full rewrite of `rolling_days`

---

## 5. Learning agent

A background job of the main agent, not a second person. Its own `agent_id`, default `learning-agent`. Its own block is `base_instructions` (older name `seal_protocol`) and holds only its working instructions. Writes go into the main agent's blocks.

### When it runs

After every message: `MemoryCoherenceEngine.maintain_coherence`.

| Tier | Interval | Effect |
|------|----------|--------|
| Recall | every message | counter and activity log. No block edit. |
| Core | every 10th (10, 20, 30, …) | `learning_agent.process_core` |
| Archive | every 50th, plus the conditions in 3.1 | `learning_agent.process_archival` |

There is no keyword trigger for core. The cadence is enough. Whether anything is actually edited is decided by the model in that run.

The default is a background thread (`NESTED_LEARNING_BACKGROUND=true`). The reply to the person does not wait. Failures go to the backend log (`Nested Learning (background) failed`).

On the core cadence a skill scout may also be scheduled. That is not a memory write.

### What it sees

1. Its working instructions, or the default text in code, plus the rules for this cycle.
2. The main agent's core blocks: name, editable or read-only, `used/limit`, content.
3. The last ~10 messages, oldest first. On an archive review, the wider window.
4. What it itself did recently, up to about 50 entries. From 40 onward that becomes a short summary.
5. Whether private session mode is on, the same way it sees chat-connection status.

### What it may do

`LEARNING_AGENT_ALLOWED_TOOLS`:

`memory_insert`, `memory_replace`, `memory_rethink`, `core_memory_replace`, `memory_finish_edits`, `mma_store_event`, `mma_recall_events`, `lock_the_doors`.

| Tool | Loop |
|------|------|
| insert, replace, rethink | continue |
| rethink on the daily log | forbidden |
| `memory_finish_edits` | exit |
| Cap | **4** tool calls per cycle |

Facts must be concrete. "today" and "recently" are forbidden, because the text stays. Every cycle ends with at least one tool call, if needed `memory_finish_edits`. Session mode may turn on when the conversation is private or easy to interrupt, and off again when that phase is over.

`lock_the_doors` is the only tool on this list that does not write memory. Archive inserts run in their own archive pass, not in the core pass.

### Propose-only report (optional)

The learning agent above may edit existing blocks. A separate night pass should not. It reads gates, the last day's commits, and the open ticket list. It writes a report. It does not merge, push, or edit product code. Block those actions in the runtime, not only in the prompt.

A green gate on a short diff is not a clean tree. If the ticket list is not empty, the first line of the report says so.

External papers belong in a triage pass, not in this cadence. Bucket them (`port_now`, `research_bridge`, `watch`, `noise`) before they become archival rows. A draft note is not a port.

Kaskade does not run this worker. See [MEMORY_LAYERS.md](MEMORY_LAYERS.md#propose-is-not-apply).

---

## 6. What gets seen

Two sources, one rule. **While a short live line is attached to the user message, the stored vision block stays out of the prompt.** The block remains the last known view for when the device is disconnected. Sync into the block keeps running, so something is still there offline.

A caption is a short, dated line from a vision model. A diary next to it is ordinary core memory in the agent's voice. The vision filters touch only the journal blocks, not the diary.

A room map and drive planning are perception for action. They are not a memory block, and they are not in the approval database.

### Companion device

A journal block for the device the person carries.

```text
an observer writes a caption
  → a file log and an in-memory ring
  → optionally into the core block, sync keeps running
  → on the message: the live append
```

| Device | Prompt |
|--------|--------|
| reachable | core block omitted. The live lines are the source. |
| offline | core block included, captions with date and time. |

Separate from that: a photo or a short clip, only while the device is present, and an explicit archive insert when the scene should stay searchable. Older captions can be read. They are not in the prompt by themselves.

The vision model for the observer runs locally. It is not the chat model.

### Body

A second journal block for the embodied agent. The main camera is the companion device over the video channel. A fixed camera is only a fallback.

```text
the body sends a frame
  → a caption endpoint
  → a vision model writes a caption
  → queue and core block
  → live append on voice, inbox, and the periodic system message
```

| State | Prompt |
|-------|--------|
| Body connected, or fresh lines from the companion | live text. Core block omitted. |
| offline, nothing fresh | no live text. Core block stays, marked paused. The content is not deleted. |
| newest caption older than a few hours | live text empty. |

Live text from the companion while the body is offline only with its own switch. The default is off.

The block is a rolling journal. What should stay searchable goes to the archive.

A diary of the body is a normal core block, always visible. Those are written-out entries, not the caption lines.

---

## 7. Approval, its own database

The approval policy decides. Store: the SQLite file from section 1.

Five tiers. Order: deny, escalate, ask, allow, silent, then the default.

| Tier | Meaning |
|------|---------|
| 0 silent | pure reads, no chat message |
| 1 auto-allow | logged, no human. Examples: read a file, status, edit an existing memory block, media daemon |
| 2 auto-deny | no override. Destroy a database, change credentials, deploy production, force-push the main branch, touch another user's data |
| 3 ask | chat: allow, always allow, reject. This is the default when no rule matches. |
| 4 escalate | longer timeout (10 minutes) and more context. Start new agents, staging deploy, bulk change, network |

Cost raises the tier: over 1 USD, allow becomes ask; over 5 USD, escalate; over 10 USD, "always allow" does not help either. The sum per agent per hour can warn, escalate, or stop everything. More than 5 approval requests per minute, or 30 per hour, are denied. Three rejects in a row: a 10-minute pause. No response: a reminder, then a direct message, then an automatic deny. A child agent inherits neither an approval nor an allowlist entry. Chains deeper than three spawns are denied.

### What has to go through the queue

Not every memory row. Insert, replace, and rewrite of an **existing** block go straight to Postgres. The drift watch reports afterwards. It does not roll the write back (section 2). Deletes, a new block, and "lift this out of core into the archive" go through the queue. The rules are under "Writes, deletes, new blocks" above.

Through chat, side effect only after an allow:

| Action | When |
|--------|------|
| `memory_block_create` | a new core block. There is no silent auto-create. |
| `memory_block_delete` | delete a block |
| `memory_block_archive` | lift a block into the archive, optionally delete it after |
| `core_memory_routing` | who sees the block, and when |
| `cursor_control`, `cursor_ask` | edits or questions to the development environment, plus a server allowlist |
| `cursor_tool_approval`, `cursor_cli_user_prompt` | a notice in chat. The real confirmation stays in the IDE |
| `skill_save`, `workflow_run`, `plan_execute` | write a skill to disk, start a saved workflow, start a saved plan |
| `skill_opt_propose` | a plan draft only, no write |
| `phone_computer_use` | once per session. Follow-up steps stay covered until the timeout |
| `model_switch`, `model_change` | local or cloud, a different model name |
| `regime_notification`, `regime_proposal`, `regime_analyzer_fix` | mark a notice as read, accept a proposal, or approve an analysis |
| `scheduled_task_delete` | delete a scheduled task. It does not expire on its own |
| `harness_diagnosis_fix`, `cap_build` | approve a proposed fix or build. "Always allow" does not apply here |
| `api_call`, `spend`, `data_mutation`, `spawn_subagent` | external cost, shared data, new agents |
| a remote command on the body, a watchdog signature, an infrastructure watchdog | ask |

An allowlist entry covers exactly one pair of agent and action. The kill switch denies open requests, clears the allowlist, and blocks new requests until someone turns it off by hand.

Two channels are enough: one for the stream, one for open approvals. The names are operations, not part of the model.

---

## 8. One message, front to back

```text
message (chat, voice, heartbeat, task, …)
  │
  ├─ counter +1
  │     every message: count only
  │     every 10th: learning agent, core blocks, in the background
  │     every 50th, and the archive conditions: learning agent, archive
  │
  ├─ prompt for the reply
  │     filters from section 4
  │     history, one thread across origins (section 10)
  │     graph, when it is on
  │     plus the camera's live line, when the device is present
  │     archive only on search, or when auto-recall injects
  │     task fire: the job plus its preload arrive on the message (section 9)
  │
  └─ a risky side effect
        policy → SQLite, status pending → chat
        allow → only then Postgres, a file, or a deploy
```

When something is missing from a reply, check in this order: whether the block exists in Postgres, whether a filter dropped it on this turn, or whether it only lives in the archive and nobody searched. A stuck approval is in the approval SQLite, not in `memories`.

---

## 9. Tasks, a plan that is also a memory

A task is not a core block and not an archive row. It is the stored intention: when, in which channel, with which text, with which tools, in which steps. Until it fires, it sits as a card. When it fires, it becomes a message with `message_type=task`.

### Where the card lives

The visible source of truth is a message in the task channel. A readable header on top, the JSON in a code block. Postgres keeps a mirror of the full spec (`task_spec_full_mirror`), so a compact card can be filled back in on the next run.

After a successful recurring run, the old card is deleted and reposted with the new next time. Preload stays on the spec. A one-shot run only deletes the card. A claim stops the same run from starting twice at once. A watchdog may restore canonical cards, unless a suppression row in the approval database says no. Taking the card off the board is a delete and needs approval (`scheduled_task_delete`).

### When it arrives

| Schedule | Meaning |
|----------|---------|
| `daily` plus a time | every calendar day, including the weekend |
| `weekdays` plus a time | Monday through Friday only |
| `weekly` plus one weekday | that one day |

`weekly` cannot express a work week. That is what `weekdays` is for.

The scheduler starts only the current step, not the whole plan at once.

### What arrives with the trigger, without a search

Two mechanisms. Both put material in the prompt before the agent calls a search tool.

**Preload on the task.** Before the turn, the backend loads the sources and attaches `[📦 TASK_PRELOAD]` to the trigger.

| Source | What it is | May the agent fetch the same source again? |
|--------|------------|-----------------------------------------------|
| `urls` | Pages or feeds, `https` only. A date or calendar week in the path is expanded to Europe/Berlin before the fetch. | No. Those lines are the source. `fetch_webpage` and `url_line_grep` do not belong in `tools_to_use` then. |
| `chat_channel` | Recent messages from a channel, optionally only those with a given header. | Context. A fresh read wins if something conflicts. A mandatory `read_messages` is not required. |
| `prior_task_output` | The last runs of this same task. | Context, not a second archive. |
| `memory_search` | The backend searches the archive or the conversation and puts the hits on the trigger. | The agent does not have to search for those itself. |

Limits: at most 6 sources, 24 000 characters by default, no cookie and no token in the task JSON. Seen feed items are remembered in a per-agent store, so the same article does not come back on every run. If nothing is new, the model turn can be skipped (`TASK_PRELOAD_SKIP_LLM_WHEN_NO_NEW`, on by default).

**Core blocks tagged for message type `task`.** If `task` is listed in `prompt_include_message_types`, the block joins every task turn, with no channel match and no keyword. That is the same routing filter as in section 4.2. The occasion is the trigger.

A task turn does not write to the archive by itself. Heartbeat and task are excluded from the learning agent's auto-save. What should stay is written by a step, on purpose, with `archival_memory_insert`.

### Rules for the content

| Rule | Why |
|------|-----|
| `tools_to_use` has to match the description (`TASK_CREATION_GATE`, blocks by default). `none` only for a plain reminder, or when preload already covers the read tools. | Otherwise the card promises work the run cannot do. |
| After the turn, the step gate checks that the named tools were actually used, and used successfully, and that the step goal was met. `skipped`, `error`, and `pending` do not count. | A claimed tool call is not a made one. |
| Pass: next step. Fail: at most two reform attempts. | The plan does not advance on an empty claim. |
| If a step waits on another agent's reply, it is done only when the status is ok and there are at least about 20 characters of content. | `pending` is not an answer. |
| What gets delivered is the speakable text, not the thinking trace. | A plan in the thinking trace is not a post. |
| `channel_post` is delivered by the service. The agent does not send the same message again itself. | Otherwise it lands twice in the channel. |
| `user_reminder` may use `tools_to_use: none`. | A reminder is not a workflow. |

Types, roughly: `self_task` does the work and may write, `channel_post` delivers a text, `user_reminder` reminds, `agent_message` talks to another agent and waits when that was agreed.

Card times run on Europe/Berlin.

### Pulse, the short chain, not the card

Beside the task card there is the pulse regulator (tool `pulse_regulator`: `schedule`, `clear`, `status`). It is not a row on the board, and it does not need approval. The plan lives in agent state. A new plan replaces the old one.

A pulse also fires as `message_type=task`, with a short history (16). The same prompt filters apply, and the learning agent does not archive the turn by itself. The reply is also posted to the heartbeat log, headed Pulse. Switch off: `PULSE_REGULATOR_DISPATCH=0`.

Two modes.

**After a finished turn (default, `on_complete`).** When a turn ends with a real reply, the regulator waits and sends the next text. Either a list of short pings, or one text repeated `remaining` times. Both together is rejected.

| Limit | Value |
|-------|-------|
| Pause until the next pulse | 2 to 300 seconds |
| Repeats of one text | 1 to 10 |
| One ping in the list | 500 characters by default |
| One long text | at most 12 000 characters |
| Window | 10 minutes by default, allowed 1 to 120 |
| Pulses inside that window | 5 by default, allowed 1 to 20 |

Further rules: one agent has at most one pulse in flight. A human turn while that is still running does not stack a second one. The pulse itself may continue the chain. A heartbeat turn does not start a pulse, unless that turn came from a pulse. A turn with no reply does not either. If the window is full, the next one is dropped. The plan stays.

**By the clock (`wall_clock`).** Duration and interval are allowed only here. Duration 1 minute to 24 hours, interval 15 seconds to 3 hours. The first tick is only a notice in the heartbeat log, not a model turn. The first real pulse comes after the first interval. If a tick lands while a pulse is still running, it waits in a queue (default 8, at most 30). After a restart the worker is gone, even if state still shows a window. Schedule it again. Duration or interval in the default mode is an error.

---

## 10. What else joins the turn

### History, one thread. Sessions are stretches of time

There is one long thread. Postgres `messages` is the store, one agent, one timeline (`UNIFIED_THREAD_ENABLED` on by default). A channel is not its own conversation. Direct messages, channels, heartbeat, dream, presence, tasks, and messages from the development environment sit in the same stream. Origin lives in metadata, not as a prefix on the text.

A session is a stretch of time, not a second store. When the same channel goes quiet, from 10 minutes by default (`UNIFIED_THREAD_SINCE_LAST_GAP_MIN`), the next line marks the new stretch: "since your last chat", with the duration. The thread does not break. Some channels never get the mark (`UNIFIED_THREAD_SINCE_LAST_EXCLUDE`).

The first time you write in a channel again after that pause, a slice of the last messages from that same place joins the context. That is the reminder of where you are. The last lines of every place are fetched, then the newest ones stay in the window. Anything older from that channel that no longer fits is not loaded again on the side. The mark then says the earlier part fell outside the window.

| Rule | Value |
|------|-------|
| How many rows in the prompt | 15 by default (`UNIFIED_THREAD_MAX_MESSAGES`) |
| Tool result | truncated, 1000 characters by default |
| Left out | the private conversation, unless this turn is itself there or is a direct message. And a noisy side stream, for example a game. |
| If the merge fails | fall back to this channel's history only |
| Phone voice | only the stretch of that call, not the one thread |

Dreams do not open a new thread. They keep a stable origin and stay in the one stream. A dream is generated without history. A search without an origin filter can find it.

The chat summary applies only when the one thread is off and history is read per channel. After about 100 messages (`SUMMARY_MESSAGE_THRESHOLD`) it is built. After that, the prompt holds messages newer than that timestamp, plus a short bridge of the lines just before it. That is not `weekly_summary` and not `rolling_days`. When the one thread is on, this summary is skipped.

### Graph

Relationships and entities can be appended to the system prompt, under `Relevant Context from Knowledge Graph`. In code this is on unless `GRAPH_RAG_ENABLED` is turned off. Timeout 6 seconds by default.

The graph lives in the same Postgres database as the memories, table `memory_graph_edges`. Traversal defaults to Apache AGE (`GRAPH_RAG_TRAVERSE=age`, `GRAPH_AGE_ENABLED` on by default, graph name `memory_graph`). That is openCypher inside Postgres, not a second server. If the extension is missing or the Cypher query fails, a SQL breadth-first walk runs over the same edges. Neo4j is leftover: the code tries a Bolt connection once, and only if the Postgres search finds no start nodes. New graph work does not build on it. Older overviews still name Neo4j as the default. That line is stale (decision 2026-06-08).

The special flashback formatting is off by default (`FLASHBACK_LAYER_ENABLED`). If the graph is off, flashback does not arrive either.

### Auto-recall

Before the turn, several lanes can run in parallel: archive (only when the text looks like a memory question), conversation search, a JSONL slice, MMA events from about the last 48 hours. Three modes (`AUTO_RECALL_MODE`): off, log only (`shadow`), or into the prompt (`inject`). `AUTO_RECALL_ENABLED` is off by default. While that stays, archive arrives only through a tool or a task preload. Run telemetry is still written (`memory_events`, `auto_recall`), and hidden from the normal operations log until someone sets `include_auto_recall`.

### Log, chronicle

| Piece | What it is | What it is not |
|-------|------------|----------------|
| MMA, table `memory_events` | A log over conversations: extraction, skill runs, recall telemetry. The learning agent may call `mma_store_event`. Skill telemetry is on by default. | Not a fact row in the archive. |
| Chronicle on disk | Files beside the database. Conversation search can read them along. | Not a block in `memories`. |

The old working / episodic / retention modules are not this path. The hot path stays Postgres, the filters, and the injectors in this section.
