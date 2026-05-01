# Project 3 — Agent Infrastructure (Canonical Reference)

**Document role:** Canonical reference for how Project 3 work is executed across machines, agents, and models. Every stage document references this file rather than redescribing the infrastructure.

**Read this document once, at project start.** Other stage documents assume familiarity with the tier model, escalation queue, GPU lockfile protocol, and machine roles defined here.

**Architecture version:** v2 (simplified after design review). The previous v1 included an automated "Tier 3b" using GPT-5.5 Pro via the OpenAI API. That was dropped to avoid (a) cost variance from runaway agent loops, (b) confidently-wrong frontier-model fixes landing without human review, and (c) integration uncertainty with new frontier models. Frontier models are now used by the human only, in Tier 4.

---

## 1. Purpose

Project 3 is a multi-month, multi-machine, multi-agent research project. Three concerns must be balanced:

1. **Cost** — Frontier model calls (GPT-5.5 Pro, Claude Opus 4.7) are expensive and unpredictable in agent loops. Use them only when a human is present.
2. **Quality** — Some tasks (debugging non-obvious failures, designing experiments, writing the final report) genuinely need a frontier model — but with human review, not autonomously.
3. **Persistence** — The project runs for weeks. Local agents need cron, memory, skills, and structured tool use, not just one-shot chat windows.
4. **GPU contention** — The same GPUs that run local Hermes/Gemma supervisors also run heavy training jobs. They cannot run simultaneously.

The architecture below is a three-tier system:
- **Tiers 1 + 2** push high-frequency cheap work to local Hermes/Gemma + OpenCode Go.
- **Tier 3** is bounded local automated coding (Hermes + Gemma 31B), with strict attempt/scope ceilings.
- **Tier 4** is the human, using ChatGPT 5.5 Pro (via Codex in VS Code) and/or Claude Opus 4.7 (via Copilot) as their tools.

A GPU lockfile prevents contention between local supervisors and heavy training jobs.

---

## 2. Hardware Inventory

| Machine | GPU | VRAM | RAM | Role |
|---------|-----|------|-----|------|
| Omega   | RTX 4070     | 8 GB  | 16 GB | Coordinator, git owner, OpenCode Go meta-supervisor, remote-API coding brain |
| Dragon  | RTX 4090     | 16 GB | 32 GB | Heavy compute (crypto pulls, RL training, AE training); Hermes + Gemma 3 31B local supervisor |
| Gamma   | RTX 5070 Ti  | 12 GB | 32 GB | API-heavy data, preprocessing GPU; Hermes + Gemma 3 31B local supervisor |

**Notes on local model:**

- User has confirmed Hermes is running `gemma4:31b` (Gemma 3 31B) successfully on Dragon and Gamma via Ollama under aggressive quantization (Q3_K_M / Q4_K_M) with CPU/RAM offloading for layers that don't fit in VRAM.
- On Omega (8GB VRAM, 16GB RAM), running Gemma 3 31B locally would require heavy CPU offloading and be impractically slow. Omega does **not** run a local Hermes supervisor for itself — Omega's logs are watched by OpenCode Go (Tier 2) directly.
- The 31B model on Dragon/Gamma occupies the GPU during inference. This conflicts with heavy training jobs. **Section 4 (GPU lockfile protocol) is the mandatory mechanism that prevents OOM errors and contention.**

---

## 3. Network and IP Configuration

**TODO at project start (user fills in current IPs):**

```
# ~/.ssh/config on Omega
Host dragon
    HostName  <DRAGON_IP_HERE>
    User      harveybc
    IdentityFile ~/.ssh/id_ed25519

Host gamma
    HostName  <GAMMA_IP_HERE>
    User      harveybc
    IdentityFile ~/.ssh/id_ed25519
```

User updates this block whenever IPs change. Stage 1.1 includes a verification step: `ssh dragon "hostname"` and `ssh gamma "hostname"` must succeed before any acquisition begins.

**IP change detection:** OpenCode Go on Omega includes a daily cron that pings the recorded IPs. If a ping fails, it adds an entry to the escalation queue tagged `infra:ip_changed` and pauses cross-machine task dispatch until the user updates `~/.ssh/config`.

---

## 4. GPU Lockfile Protocol (MANDATORY — read carefully)

### 4.1 The problem

Hermes + Gemma 3 31B occupies most of Dragon's 16GB VRAM and most of Gamma's 12GB VRAM. Heavy training jobs (RL, autoencoders, multitaper spectral) also need GPU. Running both simultaneously causes OOM errors that crash both jobs.

### 4.2 The solution

A simple lockfile coordinates GPU access between heavy training jobs and local Hermes supervisors.

**Lockfile path (per machine):** `/tmp/gpu_busy.lock`

**Lockfile contents (JSON):**

```json
{
  "owner_pid": 12345,
  "owner_command": "python train_autoencoder.py --asset btcusdt --tf 1h",
  "acquired_at": "2026-04-30T14:23:00Z",
  "expected_duration_minutes": 90,
  "stage": "2.4"
}
```

### 4.3 Heavy-job protocol

Every heavy GPU job (RL training, AE training, multitaper, EMD on long series, etc.) MUST:

1. **Before starting**, write `/tmp/gpu_busy.lock` with its PID, command, start time, expected duration, and stage.
2. **On exit (normal or abnormal)**, delete the lockfile.
3. **Use a `try/finally` or trap so the lockfile is always released**, even on crashes.

A standard helper is provided in `_scripts/lib/gpu_lock.py`:

```python
import json, os, atexit, time
from datetime import datetime, timezone

LOCKFILE = "/tmp/gpu_busy.lock"

def acquire_gpu_lock(command, expected_duration_minutes, stage):
    if os.path.exists(LOCKFILE):
        with open(LOCKFILE) as f:
            existing = json.load(f)
        raise RuntimeError(f"GPU lock held by PID {existing['owner_pid']} ({existing['owner_command']})")
    payload = {
        "owner_pid": os.getpid(),
        "owner_command": command,
        "acquired_at": datetime.now(timezone.utc).isoformat(),
        "expected_duration_minutes": expected_duration_minutes,
        "stage": stage,
    }
    with open(LOCKFILE, "w") as f:
        json.dump(payload, f)
    atexit.register(release_gpu_lock)

def release_gpu_lock():
    if os.path.exists(LOCKFILE):
        os.remove(LOCKFILE)
```

### 4.4 Hermes supervisor protocol (cron-invoked)

Each cron-invoked Tier 1 Hermes supervisor MUST:

1. Check `/tmp/gpu_busy.lock` before loading the Gemma model.
2. **If lockfile exists and is fresh (acquired <2× expected_duration ago):**
   - Skip this tick. Log "skipped: gpu busy by PID X (job Y, stage Z)" to the supervisor's status file.
   - Optional fallback: run a CPU-only summarization of the last log batch using a much smaller model or simple regex/heuristic rules.
3. **If lockfile exists but is stale (>2× expected_duration old):**
   - Assume the heavy job crashed without releasing. Log a warning. Delete the stale lockfile. Proceed with normal GPU invocation.
   - File an escalation tagged `infra:stale_gpu_lock` so the user / Tier 3 can investigate.
4. **If no lockfile:**
   - Acquire the lockfile itself (with `expected_duration_minutes: 5`, `command: "hermes_supervisor"`).
   - Run the model, produce the status report, exit.
   - The atexit handler releases the lockfile.

### 4.5 Cron frequency by phase

| Project phase | Cron frequency on Dragon/Gamma | Reason |
|---------------|-------------------------------|--------|
| Phase 1 acquisition (no GPU training) | Every 5 min | Plenty of GPU headroom |
| Phase 2 feature engineering | Every 15 min | Multitaper / EMD / AE training competes for GPU |
| Phase 3 RL experiments | Every 30 min | RL training is GPU-bound for hours |

Omega (no local Hermes) is unaffected — its supervisor role is filled by OpenCode Go at Tier 2.

The cron entries live in `_scripts/cron/`, are version-controlled, and are documented in Stage 1.1.

---

## 5. Four-Tier Agent Architecture

### Tier 1 — Per-machine local supervisors (Hermes + Gemma 3 31B, cron-invoked)

| Machine | Wrapper | Local model | Cron interval | Notes |
|---------|---------|-------------|---------------|-------|
| Dragon  | Hermes  | Gemma 3 31B (Q3/Q4 quantized via Ollama) | 5–30 min (phase-dependent) | Watches Dragon worker logs |
| Gamma   | Hermes  | Gemma 3 31B (Q3/Q4 quantized via Ollama) | 5–30 min (phase-dependent) | Watches Gamma worker logs |
| Omega   | (none — uses Tier 2 OpenCode Go directly) | n/a | n/a | Omega's GPU is too small for 31B |

**What Tier 1 does:**

- Tails worker logs in `~/Documents/financial_data/_logs/<machine>/`
- On each cron tick: checks GPU lockfile, loads model if free, produces a structured JSON status report, exits
- Detects: stalled processes, repeated errors, unexpected log silence, validation failures
- Writes: `~/Documents/financial_data/_logs/supervisor_reports/<machine>_status.json`

**Why Hermes wrapper specifically:** persistent context across cron ticks via Hermes's skill/memory system. The agent learns common log patterns over project lifetime so future occurrences resolve faster. We do not use plain `ollama run` because we lose skill accumulation.

**What Tier 1 does NOT do:** make decisions, modify code, modify the plan, contact remote APIs. Tier 1 is observational + light triage only.

### Tier 2 — Meta-supervisor / orchestrator (OpenCode Go on Omega, cron-invoked)

OpenCode Go on Omega, capped to one invocation every 10–15 minutes via cron.

**What Tier 2 does:**

- Reads the two Tier 1 status reports (Dragon, Gamma)
- Reads Omega's own worker logs directly (Omega has no local Tier 1)
- Aggregates into `~/Documents/financial_data/_logs/supervisor_reports/global_status.md`
- Maintains the escalation queue: `_logs/supervisor_reports/escalation_queue.json`
- Dispatches new acquisition / preprocessing tasks to idle machines per the active stage doc
- Commits status reports to the git repo on Omega
- For genuine anomalies, adds an entry to the escalation queue and notifies Tier 3

**Why capped to 10–15 min cron:** OpenCode Go is paid-per-call. High-frequency log watching is Tier 1's job. Tier 2 only runs when there's enough new information to justify a paid model call.

**Why OpenCode Go specifically:** good at multi-file repo reasoning, structured output, coordinating across machines via SSH. The orchestration logic is stateless across cron ticks (state lives in `escalation_queue.json` and the git repo), so it doesn't need a Hermes wrapper for memory.

### Tier 3 — Bounded local automated coding (Hermes + Gemma 31B, escalation-triggered)

Single tier handler for code/data anomalies that Tier 1 + Tier 2 cannot resolve via known skills. Uses the local Hermes + Gemma 31B already running on Dragon and Gamma (whichever has the lighter current load, decided by Tier 2). Does NOT call any remote frontier model.

**What Tier 3 does:**

- Receives escalations from Tier 2 with `category` in `{code_bug, data_anomaly, infra}`
- Reads the relevant logs, code files, and prior escalation queue history
- Attempts a fix following these strict ceilings:
  - **Max 3 attempts per escalation** (each attempt = one diagnosis-edit-test cycle)
  - **Max 2 files modified per attempt**
  - **Max 30 minutes wall-clock per attempt**
  - **Max 0 git commits without passing the project's existing tests** (it can write patches, but a commit only happens when tests pass; otherwise the patch is staged for human review)
- Writes a confidence indicator with every resolution attempt (0.0–1.0)
- If any attempt has confidence < 0.7, OR all 3 attempts fail, OR the task is outside the allowed scope (touches >2 files, designs new architecture, requires multi-file repo reasoning, is plan synthesis or final-report writing) → marks the escalation `requires_human` and prepares a structured handoff document for Tier 4

**Why bounded:** local models confidently apply wrong fixes when given unbounded budgets. The 3-attempt ceiling, file-count ceiling, and confidence threshold prevent runaway "agent thrash" where the model accumulates broken commits.

**Why no automated frontier API:** runaway agent loops with frontier models can burn $50–$200 in tokens overnight. They also produce confident-but-wrong fixes that look plausible to local reviewers but fail subtly in production. Frontier models go through Tier 4 with a human in the loop.

**What Tier 3 does NOT do:** modify the project plan documents, change stage gates, make subscription/data-source decisions, write Phase 3 final reports, or design experimental pre-registrations. All of those route to Tier 4 unconditionally.

### Tier 4 — Human-in-the-loop with frontier models as tools

The user, using whichever frontier tools they prefer:

- **ChatGPT Pro Plus + Codex in VS Code (GPT-5.5 Pro)** — for hard coding tasks, debugging across many files, design questions, final report drafting. Recommended primary Tier 4 tool given current benchmark performance.
- **VS Code Copilot Opus 4.7** (15× usage rate) — alternative primary or second opinion. User chooses per task.
- **Claude Pro / Max** (manual chat) — for planning conversations, design review, second opinions on Tier 3 / Codex / Copilot output.

**The Tier 4 workflow:**

1. Tier 3 (or Tier 2 directly, for plan/synthesis tasks) prepares a structured handoff document: the bug or task, what was tried, what failed, the relevant code files, the relevant logs, and a clear question for the human. This document lives at `_logs/supervisor_reports/tier4_handoffs/<escalation_id>.md`.
2. User opens the handoff, copies the relevant context into ChatGPT 5.5 Pro / Codex / Copilot.
3. User reviews the frontier model's response, edits if needed, applies the fix.
4. User updates the escalation queue entry with resolution status and commits.

**Tier 4 is invoked when:**

- Tier 3 marks `requires_human`
- Task is `category=plan_decision`, `category=synthesis`, or `category=final_report`
- Severity `blocker` (always notifies human immediately, even if Tier 3 thinks it can handle it)
- Stage gate approvals
- Experimental design pre-registration sign-off
- Subscription approve/cancel decisions

**Cost discipline:** ChatGPT Pro Plus is flat ~$200/month. Copilot Opus 4.7 has a 15× usage quota that depletes fast. **No metered API billing anywhere in the architecture** — bills are predictable.

---

## 6. Tier 3 → Tier 4 Routing Rules

Replaces the prior Tier 3a/Tier 3b threshold table. Now a simpler binary: does Tier 3 try, or does it hand off to Tier 4 immediately?

**Route to Tier 3 (try local Hermes + Gemma 31B) when ALL hold:**

- `category` ∈ {`code_bug`, `data_anomaly`, `infra`}
- `severity` ∈ {`low`, `medium`, `high`} (NOT `blocker`)
- Estimated scope ≤ 2 files
- Task does not require multi-file repo reasoning
- Task is not plan synthesis, design, or report writing

If Tier 3 attempts and any of these fire — confidence < 0.7 on best attempt, all 3 attempts failed, scope expands beyond 2 files mid-attempt — it marks `requires_human` and routes to Tier 4.

**Route to Tier 4 immediately (skip Tier 3) when ANY hold:**

- `category` ∈ {`plan_decision`, `plan_decision_proposal`, `synthesis`, `final_report`}
- `severity` = `blocker`
- Task touches >2 files or requires multi-file repo reasoning
- Task requires designing new architecture, validation logic, or experimental design
- Stage gate approval needed
- Subscription decision needed

**Self-criticism rule (mandatory for Tier 3):** every resolution attempt by Tier 3 includes a confidence indicator (0.0–1.0) and a list of unverified assumptions. The local Gemma model is instructed via its system prompt to err toward low confidence — false negatives (handing off when it could have solved) are cheap; false positives (committing wrong fixes) are expensive.

---

## 7. Information Flow

```
Per-machine raw logs (Python workers)
        |
        v
Tier 1: Dragon + Gamma local Hermes/Gemma supervisors (cron, GPU-lock-aware)
        |  Omega logs read directly by Tier 2
        |
        +--> _logs/supervisor_reports/dragon_status.json
        +--> _logs/supervisor_reports/gamma_status.json
        |
        v
Tier 2: OpenCode Go meta-supervisor on Omega (every 10-15 min via cron)
        |
        +--> _logs/supervisor_reports/global_status.md   (human-readable)
        +--> _logs/supervisor_reports/escalation_queue.json  (machine-readable)
        |
        v  (escalations only, with category + severity routing)
Tier 3: Hermes + local Gemma 31B (bounded: max 3 attempts, max 2 files, max 30min/attempt)
        |    Routes here ONLY for code_bug / data_anomaly / infra of low/medium/high severity
        |    AND scope ≤ 2 files AND not synthesis/design/report
        |
        v  (when Tier 3 confidence < 0.7, attempts exhausted, or scope outside ceilings,
            OR when escalation is blocker / plan_decision / synthesis / final_report)
Tier 4: User with frontier tools as choice:
          - ChatGPT Pro Plus + Codex in VS Code (GPT-5.5 Pro) — recommended primary
          - VS Code Copilot Opus 4.7 (15× quota)
          - Claude Pro / Max chat
        Reads structured handoff doc at _logs/supervisor_reports/tier4_handoffs/<id>.md
```

---

## 8. Escalation Queue Schema

`_logs/supervisor_reports/escalation_queue.json`:

```json
{
  "queue": [
    {
      "id": "esc-2026-04-30-001",
      "created_at": "2026-04-30T14:23:00Z",
      "source_machine": "dragon",
      "source_tier": "tier1_local_supervisor",
      "category": "code_bug | data_anomaly | infra | plan_decision | plan_decision_proposal | synthesis | final_report",
      "severity": "low | medium | high | blocker",
      "summary": "Binance fetcher returning 429 for >5 minutes despite backoff",
      "evidence_path": "_logs/dragon/binance_fetch_2026-04-30.log",
      "files_touched_estimate": 1,
      "assigned_tier": "tier3_local | tier4_human",
      "status": "open | in_progress | resolved | requires_human",
      "tier3_attempts": 0,
      "tier3_last_confidence": null,
      "tier3_unverified_assumptions": [],
      "tier4_handoff_path": null,
      "resolution": null,
      "resolution_commit": null
    }
  ]
}
```

**Severity definitions:**

- `low`: cosmetic, advisory, can wait an hour
- `medium`: degrades quality but pipeline still progresses
- `high`: blocks progress within current stage but other stages can continue
- `blocker`: halts the entire project pipeline; notify user immediately

**Category routing summary** (full rules in §6):

| Category | Routes to |
|----------|-----------|
| `code_bug`, `data_anomaly`, `infra` (low/med/high, ≤2 files) | Tier 3 first |
| `code_bug`, `data_anomaly`, `infra` (>2 files OR `blocker`) | Tier 4 directly |
| `plan_decision`, `plan_decision_proposal` | Tier 4 directly |
| `synthesis`, `final_report` | Tier 4 directly |

---

## 9. Auto-validation Policy (per user direction)

**Mode: full auto.** When the user confirms a manual task is complete (e.g., "Stage 1.3 manual tasks done"), agents proceed through all validation, deliverable generation, and downstream stage prep automatically. Only blockers ping the user.

**A blocker is:**

- Validation failure that cannot be auto-resolved (e.g., HistData zips corrupt, FRED key revoked, machine unreachable)
- Coverage gap below the catalog's minimum-acceptable threshold
- An escalation queue entry with severity `blocker`

**Non-blockers (advisory failures, partial coverage within tolerance, cosmetic issues) are documented and proceed.**

---

## 10. Stage Execution Pattern (applies to ALL stages)

Every stage document follows this pattern:

1. **User confirms manual prerequisites complete** (when applicable). Examples: HistData downloads done, API keys provided, machines online.
2. **OpenCode Go on Omega (Tier 2) dispatches stage tasks** to the appropriate machine(s) per the stage doc's machine assignment table.
3. **Python workers run on assigned machines.** Local Hermes supervisors (Tier 1) watch logs, respecting the GPU lockfile.
4. **On any anomaly, escalation is filed** and routed per Section 6.
5. **Stage deliverable is auto-generated** by Tier 2 from validated worker outputs.
6. **User gate:** user reviews the deliverable. Only then does the next stage start.

The user does **not** manually run validation commands, file counts, or coverage checks. Those are Tier 1 + Tier 2's job. The user reviews the deliverable produced by the agents.

---

## 11. What Replaces Manual Commands in Stage Docs

Earlier versions of the stage documents asked the user to run commands like `ls ~/Downloads/histdata/eurusd/ | wc -l` to count files. Those have been removed.

The new pattern is:

> When user confirms "Stage X manual work complete," OpenCode Go on Omega dispatches the corresponding validation task to the appropriate machine. The Tier 1 supervisor watches the validation logs. The validation script counts files, checks coverage, verifies schemas, and writes results into the stage deliverable. User reviews the deliverable.

If you find any stage doc that still contains a `wc -l` or `ls | wc` instruction directed at the user, treat it as a documentation bug and file an escalation tagged `plan_decision_proposal`.

---

## 12. Cost Discipline Rules

**Rule A.1 — Prefer cheap models for high-frequency work.**
Tier 1 (local Gemma 31B, cron-invoked) handles all high-frequency log watching. Tier 2 (OpenCode Go) is capped to a 10–15 min cron tick. Tier 3 (local Gemma 31B, bounded) is escalation-only. Tier 4 (human + frontier tools) is human-initiated only. **No metered API billing in the automated path.**

**Rule A.2 — Skills > re-prompting.**
Hermes wrappers accumulate skills over the project lifetime. When a Tier 1 supervisor sees the same anomaly pattern three times, it should encode a skill so future occurrences resolve without escalation.

**Rule A.3 — AI subscription costs are predictable, not metered.**
The $500/month cap from Master Plan Rule M.10 applies to data subscriptions only. AI tool costs are tracked separately in `_metadata/ai_subscriptions.json`. Current expected stack:
- ChatGPT Pro Plus: ~$200/month (flat, includes Codex in VS Code with GPT-5.5 Pro)
- VS Code Copilot Opus 4.7: existing subscription with 15× usage quota
- OpenCode Go: per its current billing (Tier 2 only, capped at one call per 12 min)
- No OpenAI API account, no Anthropic API account → no metered token billing

**Rule A.4 — Honest self-criticism.**
Every agent (Tier 1 through Tier 3) operates with the understanding that it can be wrong. When a local Gemma summarizes Dragon's logs, it includes a confidence indicator. When Tier 3 attempts a fix, the response template requires confidence (0.0–1.0) and a list of unverified assumptions. The local Gemma's system prompt instructs it to err toward low confidence — false negatives (handing off when it could solve) are cheap; false positives (committing wrong fixes) are expensive. The user is the final arbiter; agents do not self-confirm correctness.

**Rule A.5 — No silent skipping.**
If a Tier 1 cron tick is skipped because the GPU lock is held, the supervisor still writes a status entry recording the skip. Long runs of skipped ticks (e.g., >6 consecutive) trigger an escalation tagged `infra:supervisor_starved` so the user knows training is monopolizing the GPU longer than expected.

**Rule A.6 — Tier 3 ceilings are not negotiable.**
Tier 3 has hard ceilings (3 attempts, 2 files per attempt, 30 min wall-clock). These are mechanical limits enforced by the calling script, not soft guidelines for the model. Bounded budgets prevent runaway agent loops where the model accumulates broken commits.

---

## 13. Agent Setup Bootstrap (Stage 1.1 task)

Stage 1.1 (Storage Architecture) is extended to also bootstrap the agent infrastructure. The bootstrap steps are:

1. **Verify SSH config:** `ssh dragon "hostname"` and `ssh gamma "hostname"` must succeed.
2. **Verify Hermes installation on Dragon and Gamma:** `ssh dragon "hermes --version"` and same on Gamma. If missing, the bootstrap halts and instructs the user how to install Hermes (Hermes installation is out of scope for this plan because it predates Project 3).
3. **Verify Ollama + Gemma model availability:** `ssh dragon "ollama list | grep gemma"` should show the 31B model. Same on Gamma.
4. **Install GPU lockfile helper:** copy `_scripts/lib/gpu_lock.py` to all three machines.
5. **Install cron entries:** the supervisor cron jobs go to `/etc/cron.d/project3_supervisor` on Dragon and Gamma. The OpenCode Go cron job goes to `/etc/cron.d/project3_orchestrator` on Omega. Cron files are version-controlled in `_scripts/cron/`.
6. **Initialize escalation queue:** `_logs/supervisor_reports/escalation_queue.json` is created with empty queue.
7. **Verify OpenCode Go on Omega:** `which opencode-go` and a test invocation that writes a "hello" entry to `global_status.md`.
8. **Initialize Tier 4 handoff folder:** `mkdir -p _logs/supervisor_reports/tier4_handoffs/`. This is where Tier 3 stages structured handoff documents for the user.
9. **Confirm Tier 4 tools are available to the user:**
   - VS Code with Codex (if user is on ChatGPT Pro Plus): user manually verifies in their IDE.
   - VS Code with Copilot Opus 4.7: user manually verifies.
   - Both are user-side checks; bootstrap just records the user's confirmation.

If any of steps 1–8 fail, Stage 1.1 halts with a clear error and an escalation queue entry tagged `infra:bootstrap_failed`. Step 9 is informational — the bootstrap completes even if Tier 4 tools aren't yet configured, but the user is reminded they'll be needed when Tier 3 hands off its first escalation.

---

## 14. Open Items for User

The following items are not yet resolved and are tracked here:

1. **ChatGPT Pro Plus subscription** — recommended for Tier 4 (gives Codex in VS Code with GPT-5.5 Pro). Optional but strongly suggested. ~$200/month flat.
2. **OpenCode Go subscription credentials** — user must confirm OpenCode Go is active on Omega.
3. **Current IPs for Dragon and Gamma** — fill in `~/.ssh/config` per Section 3.
4. **AI subscription tracker** — user populates `_metadata/ai_subscriptions.json` with current AI tool costs once known. No fixed cap because there is no metered API; costs are predictable subscription fees.

**Explicitly NOT needed (vs. v1 of this doc):**
- ❌ OpenAI API key — no automated frontier API access in v2 architecture
- ❌ Anthropic API key — same reason
- ❌ AI API monthly cost ceiling — there are no metered AI APIs in the loop
