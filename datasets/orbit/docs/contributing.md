---
id: contributing
title: Contributing to Orbit
section: Project
applies_to: "all"
updated: 2026-08-11
---

# Contributing to Orbit

Thanks for helping! Orbit is maintained by a small group of volunteers, and every bug report,
docs fix and pull request helps. This page covers how to file good issues, set up a dev
environment, and get a PR merged.

## Maintainers

| Handle | Focus |
|---|---|
| @mara-k | `core`, `scheduler`, release management |
| @devon-li | `flows`, `results`, `retries` |
| @sam-okafor | `broker-redis`, `broker-postgres`, `broker-sqs` |
| @ines-v | `dashboard`, `auth`, `observability`, `docs` |

The `cli` component is shared. Ping whoever owns the subsystem the command touches.

## Filing an issue

Before opening one, search existing issues for your error code (for example `ORB-1101`).
Most problems have been reported before, and duplicates get closed with a link to the original.

A good bug report includes:

- the Orbit version and Python version, and the broker with its version;
- the output of `orbit doctor`;
- your `orbit.toml` (or, on 2.x, `orbit.ini` and the relevant `ORBIT_*` variables) **with
  secrets removed**;
- the first `ORB-` code in the logs, and a stack trace if there is one;
- a minimal reproduction.

> **Note:** Never paste real credentials, customer data or production hostnames. Use
> placeholders like `redis://user:REDACTED@redis.example.com:6379/0`. Security vulnerabilities go
> to security@example.com, not the issue tracker ([security.md](security.md)).

## Labels

Maintainers triage new issues within a few days and apply labels from four families.

| Family | Values |
|---|---|
| `type:` | `bug`, `feature`, `question`, `docs` |
| `comp:` | `core`, `scheduler`, `flows`, `broker-redis`, `broker-postgres`, `broker-sqs`, `cli`, `dashboard`, `retries`, `results`, `observability`, `auth`, `docs` |
| `severity:` (bugs only) | `S1` to `S4`, see below |
| `version:` | The affected minor version, for example `version:3.2` |

**Severity**

| Level | Meaning | Example |
|---|---|---|
| S1 | Data loss, security issue, or a production outage with no workaround | Jobs silently dropped |
| S2 | Major feature broken, with a painful workaround | Reconnect storm after Redis failover |
| S3 | Bug with a reasonable workaround | OIDC loop fixed by `X-Forwarded-Proto` |
| S4 | Cosmetic or minor | Typo in a CLI help message |

Usage questions are welcome as `type:question`, but a reply may just be a link to the right
docs page.

## Development setup

```bash
git clone https://git.example.com/orbit/orbit.git
cd orbit
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker compose -f dev/compose.yaml up -d   # Redis, Postgres and an SQS emulator
pytest -q
```

Develop on Python 3.12. CI tests every supported version up to 3.12. Python 3.13 isn't supported
yet ([faq.md](faq.md)), so please don't submit 3.13-only syntax.

### Repository layout

```text
src/orbit/
  core/            # Orbit app, jobs, workers, queues        -> comp:core
  scheduler/       # cron schedules, delays                  -> comp:scheduler
  flows/           # Flow, step, run state                   -> comp:flows
  brokers/redis/   brokers/postgres/   brokers/sqs/          -> comp:broker-*
  retries/  results/  observability/  auth/
  dashboard/       # web UI served by `orbit dashboard`      -> comp:dashboard
  cli/             # `orbit worker`, `orbit dlq`, `orbit doctor`, ...
docs/              # these pages                             -> comp:docs
```

## Pull requests

1. For anything larger than a bug fix, open or comment on an issue first, so nobody spends a
   weekend on a change that won't be merged.
2. Branch from `main`. Fixes for the 2.x line go to the `2.9.x` branch, and **only security
   fixes** are accepted there until 2.x reaches end of life on 2026-12-31.
3. Add tests. Broker changes need tests against all three brokers. CI runs them.
4. Run `ruff check .`, `ruff format .` and `pytest`.
5. Add a line under "Unreleased" in `CHANGELOG.md`, which is published as
   [changelog.md](changelog.md).
6. One maintainer approval is required. Changes to `core` or a broker need two.

Commit messages use the component as a prefix, for example
`broker-redis: add jitter to reconnect backoff`.

## Docs contributions

Docs live in `docs/` as Markdown with YAML front matter:

```yaml
---
id: troubleshooting-broker
title: Troubleshooting broker problems
section: Troubleshooting
applies_to: "all"      # "3.x", "2.x" or "all"
updated: 2026-08-11
---
```

Set `applies_to` honestly. Readers filter by version, and a 2.x answer shown to a 3.x user, or
the other way round, is worse than no answer. Link to other pages by file name, for example
`[leases](leases-and-heartbeats.md)`. Error codes and config keys must match
[error-codes.md](error-codes.md) and [configuration-reference.md](configuration-reference.md)
exactly.

## Releases

@mara-k cuts releases. Minor releases ship roughly every three months, and patch releases go out
as needed. Every release is tagged, signed, and announced in the changelog.
