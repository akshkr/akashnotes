---
id: cli-reference
title: CLI reference
section: Reference
applies_to: "3.x"
updated: 2026-10-26
---

# CLI reference

The `orbit` command is installed with the library. Every command loads `orbit.toml` from the current working directory, using the same rules as the Python API (see [Configuration reference](configuration-reference.md)). Run `orbit --help` or `orbit <command> --help` for built-in help, and `orbit --version` to print the installed version.

| Command | Purpose |
|---|---|
| [`orbit worker`](#orbit-worker) | Start a worker process |
| [`orbit flows run`](#orbit-flows-run) | Start a flow run |
| [`orbit flows status`](#orbit-flows-status) | Show the state of a flow run |
| [`orbit dlq list / replay / purge`](#orbit-dlq) | Inspect and manage the dead-letter queue |
| [`orbit doctor`](#orbit-doctor) | Check the broker, config and versions |
| [`orbit migrate-config`](#orbit-migrate-config) | Convert a 2.x `orbit.ini` into `orbit.toml` |
| [`orbit dashboard`](#orbit-dashboard) | Serve the web dashboard |

## Exit codes

Every command uses the same exit codes:

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | The command ran and failed (broker unreachable, a doctor check failed, unknown job ID, ...) |
| `2` | Usage error (unknown flag, missing argument) |

## `orbit worker`

```bash
orbit worker --queues default,high --concurrency 8
```

| Option | Default | Description |
|---|---|---|
| `--queues` | `default` | Comma-separated list of queues to consume |
| `--concurrency` | `[worker] concurrency` (4) | Jobs this process runs in parallel |

Other worker settings, such as prefetch, lease and heartbeat, come only from [`orbit.toml`](configuration-reference.md#worker).

**Signals.** On `SIGTERM` or `SIGINT`, the worker stops taking new jobs, hands back any prefetched jobs that have not started, and waits for running jobs to finish. A second signal stops it immediately. Running jobs are then picked up again by another worker once their lease expires. Give the worker a shutdown grace period at least as long as your longest job; see [Docker](deployment-docker.md) and [Kubernetes](deployment-kubernetes.md).

> **Note:** On **Windows**, `orbit worker` currently ignores `SIGTERM`, so service managers cannot stop it gracefully. Stop it with Ctrl+C in an interactive console, or run workers in Linux containers. This is a known open issue.

## `orbit flows run`

```bash
$ orbit flows run nightly-rollup
started run fr_01JBA2X0QK (flow=nightly-rollup, steps=4)
```

This starts a run of a registered [flow](flows-overview.md) **with no inputs**, so steps get only the default values of their parameters. To start a run that needs inputs, call `flow.run(...)` from Python. The command prints the run ID and exits straight away. It does not wait for the run to finish.

## `orbit flows status`

```bash
orbit flows status <run_id>
```

Prints the run state and a per-step table: state, attempt count and the job ID of the latest attempt. If the run record has expired (after `[results] ttl_days`) or never existed, it prints `unknown run` and exits with code `1`. For sample output, see [Flow steps and state](flows-steps-and-state.md#checking-a-run).

## `orbit dlq`

The [dead-letter queue](dead-letter-queue.md) holds jobs that ran out of retries (`ORB-1301 RetryExhausted`).

```bash
$ orbit dlq list
JOB ID     JOB              FLOW RUN       ERROR     FAILED AT
j_61c0aa   send_receipt     -              ORB-1301  2026-10-25T22:01:17Z
j_61c0f3   sync_invoices    -              ORB-1301  2026-10-25T22:04:51Z

$ orbit dlq replay j_61c0aa
replayed j_61c0aa -> j_61d102

$ orbit dlq purge
Delete 1 dead-lettered job(s)? This cannot be undone. [y/N]: y
purged 1 job(s)
```

- `list` prints every DLQ entry, oldest first.
- `replay <job_id>` puts the job back on its original queue as a **new** job with a new ID and the attempt count reset to zero. The original arguments and idempotency key are kept. If the job was a flow step, the replay also resumes its flow run (see [Error handling in flows](flows-error-handling.md)).
- `purge` deletes **all** DLQ entries after asking for confirmation. In scripts that have no TTY, pipe the answer in: `yes | orbit dlq purge`.

## `orbit doctor`

```text
$ orbit doctor
orbit 3.2.1 (python 3.12.6)
[ok]   config    orbit.toml loaded (7 sections)
[ok]   broker    redis://redis:6379/0 reachable (PING 0.4 ms)
[warn] worker    heartbeat_seconds=120 is more than lease_seconds/3 (300)
[warn] env       ORBIT_CONCURRENCY is set but ignored in 3.x
[ok]   versions  6 workers online, all 3.2.1
```

| Check | Fails when |
|---|---|
| `config` | `orbit.toml` is missing or invalid, e.g. `ORB-1802 UnknownConfigKey` |
| `broker` | The broker cannot be reached (`ORB-1001`) or rejects the credentials (`ORB-1002`) |
| `results` | `[results] backend` does not match the broker type |
| `versions` | Workers report different Orbit versions |

Warnings do not change the exit code. Any failed check makes `doctor` exit with code `1`, so it can serve as a CI gate or a readiness probe.

## `orbit migrate-config`

```bash
orbit migrate-config orbit.ini
```

Converts a 2.x `orbit.ini` into `orbit.toml` in the current directory. It refuses to run if `orbit.toml` already exists. It does not read `ORBIT_*` environment variables. Unparseable input fails with `ORB-1801 ConfigMigrationError`. Use 3.0.3 or later, because the 3.0.1 converter dropped `[retries]`. The full procedure is in [Migrating from 2.x to 3.x](migrating-2-to-3.md).

## `orbit dashboard`

```bash
orbit dashboard --port 7777
```

| Option | Default | Description |
|---|---|---|
| `--port` | `7777` | HTTP port to listen on |

Authentication comes from the `[dashboard]` section. With `auth = "token"`, the startup log prints a sign-in URL. See [Dashboard](dashboard.md) and [Dashboard OIDC sign-in](dashboard-auth-oidc.md).
