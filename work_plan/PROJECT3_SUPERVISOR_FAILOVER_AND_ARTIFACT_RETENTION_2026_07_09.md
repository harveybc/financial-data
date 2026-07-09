# Project3 Supervisor Failover And Artifact Retention

Date: 2026-07-09

## Purpose

Project3 weekly walk-forward state must survive coordinator failure and must be
portable across omega, dragon, and gamma. GitHub stores code, specs, and
reproducible instructions. The live SQLite pool and heavy run artifacts are not
GitHub assets; they are backed up and replicated between machines.

## Canonical State

Primary pool DB:

```text
/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/project3_weekly_pool.sqlite
```

This SQLite file is the canonical source for:

- queued/running/deferred/done subjobs;
- job configuration JSON;
- weekly metrics;
- annual OLAP rollups;
- artifact metadata;
- machine heartbeats.

The DB is too large for normal GitHub use. It must be backed up as a compressed
failover pack instead of committed.

## Backup Command

Run from any machine with the repos available:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python \
  /home/harveybc/Documents/GitHub/agent-multi/tools/project3_weekly_pool_backup.py \
  --label manual_failover \
  --copy-to /home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest
```

The tool creates:

- `project3_weekly_pool.sqlite.gz`: compressed consistent SQLite snapshot;
- `schema.sql`: schema for audit/rebuild;
- `manifest.json`: checksums, row counts, status counts;
- `*.csv.gz`: portable exports of jobs, subjobs, machine heartbeats, and OLAP
  views.

Recommended replication targets:

```bash
rsync -az /home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest/ \
  dragon:/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest/

rsync -az -e 'ssh -p 22022' \
  /home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest/ \
  192.0.2.16:/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest/
```

## Supervisor Failover Procedure

1. Stop the current coordinator API/dashboard/supervisor if it is still alive.
2. On the new coordinator, restore the DB:

```bash
cd /home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool
cp project3_weekly_pool.sqlite project3_weekly_pool.before_failover.sqlite 2>/dev/null || true
gzip -dc failover_latest/project3_weekly_pool.sqlite.gz > project3_weekly_pool.sqlite
sqlite3 project3_weekly_pool.sqlite 'pragma integrity_check;'
```

3. Start the pool API on the new coordinator with the restored DB and the same
   token file path, or update remote workers to point at the new coordinator
   Tailscale/LAN URL.
4. Requeue stale `running` jobs whose heartbeat belongs to the failed machine.
5. Start remote workers after the API health endpoint returns OK.
6. Verify status from live SSH/process/GPU checks, not DB heartbeats alone.

## Artifact Retention Policy

Metrics are preserved in OLAP. Heavy training artifacts are only retained when
they are useful for reproduction, warm-start, or handoff.

Preserve:

- `policy.zip` for top candidates and warm-start parents;
- `results.json`;
- `config_out.json`;
- `evidence.json`;
- context embedding manifests;
- OLAP DB and failover backup exports.

Prunable after backup:

- `return_traces/*.csv`;
- generated `context_embedding/input_with_context_embedding.csv`;
- `subprocess_stdout*.log`;
- `training_progress.json`;
- local package caches and old system journals.

Use dry-run first:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python \
  /home/harveybc/Documents/GitHub/agent-multi/tools/project3_weekly_prune_artifacts.py
```

Execute only after a fresh failover backup exists:

```bash
/home/harveybc/anaconda3/envs/tensorflow/bin/python \
  /home/harveybc/Documents/GitHub/agent-multi/tools/project3_weekly_prune_artifacts.py \
  --execute
```

The pruner skips active running subjob directories by default.

## Current Operational Notes

- Omega is currently safe as API/dashboard coordinator only until the CUDA
  driver/userspace mismatch is fixed.
- Dragon and gamma workers are configured as persistent API workers.
- Gamma disk pressure is caused primarily by Project3 run artifacts, not games.
- Gamma also has a large Windows NTFS partition that may be used as cold
  archive storage, but active training output should remain on Linux/ext4 when
  possible.

## Verified Snapshot - 2026-07-09 13:26 COT

Latest portable failover pack:

```text
/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/failover_latest
```

Snapshot source:

```text
/home/harveybc/Documents/GitHub/financial-data/experiments/weekly_walkforward_pool/backups/20260709T182513Z_failover_current_20260709T182513Z
```

Pack contents were gzip-verified on omega, dragon, and gamma. The manifest row
counts at backup time were:

- `jobs`: 1232;
- `subjobs`: 26976;
- `machine_heartbeats`: 3;
- `weekly_result_olap`: 16121;
- `weekly_result_test_year_olap`: 841;
- `weekly_result_validation_year_olap`: 892;
- `weekly_result_full_year_protocol_olap`: 192;
- `weekly_result_artifact_olap`: 55652.

Artifact pruning after this backup removed only reproducible local files:

- omega: 35.854 GiB, 44029 files;
- dragon: 42.1343 GiB, 56216 files;
- gamma: 47.1467 GiB, 59490 files.

Preserved files include all `policy.zip`, `results.json`, `config_out.json`,
`evidence.json`, context embedding manifests, and the replicated OLAP/SQLite
backup pack.
