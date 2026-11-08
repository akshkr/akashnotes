---
id: dashboard
title: Dashboard
section: Dashboard
applies_to: "3.x"
updated: 2026-10-25
---

# Dashboard

The Orbit dashboard is a small web UI for watching queues, workers, flows and the dead-letter queue, and for acting on them. It connects to the broker and result backend in your `orbit.toml`, so it shows the same data your workers use. Nothing is collected separately.

```bash
orbit dashboard --port 7777
```

Then open `http://localhost:7777`. The dashboard only needs network access to the broker. It does not talk to the workers directly.

## What you can see

| Page | Shows | Actions |
|---|---|---|
| **Queues** | Depth per queue and priority, enqueue and completion rates over the last hour, oldest waiting job | none |
| **Jobs** | Look up a job by ID: arguments, attempts, last error with its `ORB-` code, result | Copy the job as a `.enqueue()` snippet |
| **Dead letters** | Every DLQ entry with its error and failure time | Replay one, replay a selection, purge all |
| **Flows** | Recent flow runs and a graph view of each run, coloured by step state | Open a step's job; replay a failed step |
| **Workers** | Online workers, their queues, concurrency, version and last heartbeat | none |
| **Schedules** | Cron schedules with the last and next run times | none |

The Workers page flags any worker whose last heartbeat is older than two `heartbeat_seconds` intervals. It also highlights workers running a different Orbit version from the majority. That is a common source of `ORB-1503 FlowStateCorrupt` during upgrades.

Job results and flow graphs come from the [result backend](results-backend.md). With `[results] backend = "none"`, the Jobs page shows only the state and attempts, and the Flows page is hidden.

## Authentication

Every page requires sign-in. Two modes are available, chosen with `[dashboard] auth`:

```toml
[dashboard]
auth = "token"     # default
```

### Token mode (default)

With `auth = "token"`, the dashboard **generates a random access token every time it starts** and prints a sign-in URL to its log:

```text
$ orbit dashboard --port 7777
orbit dashboard 3.2.1 listening on :7777
sign in: http://localhost:7777/login?token=Qm9hdF9yZWQtd2luZG93LTQy
```

Opening that URL sets a session cookie. The token is held only in memory, so:

- **Restarting the dashboard invalidates every session.** Everyone has to use the new URL from the log.
- **Each replica has its own token.** If you put two replicas behind a load balancer, sessions only work on the replica that issued them, and users bounce between "signed in" and "signed out". Run a single replica in token mode, or switch to OIDC.

Token mode suits a laptop, a staging box, or a single operator reaching it over SSH port forwarding. It is not meant for a dashboard that a whole team shares.

A wrong or old token returns `401` and logs `ORB-1701 DashboardAuthFailed` with the client IP. Repeated `ORB-1701` from one address usually means someone bookmarked a URL from before the last restart.

### OIDC mode

With `auth = "oidc"`, users sign in through your identity provider (Okta, Entra ID, Keycloak, Google Workspace and so on). Sessions survive restarts and work across replicas. The setup steps and the reverse-proxy caveat are in [Dashboard OIDC sign-in](dashboard-auth-oidc.md).

## Permissions

The dashboard has **no roles**. Anyone who can sign in can replay and purge dead letters. If only some people should be able to do that, limit who can reach the dashboard in the first place: put it on a private network, restrict which users your identity provider assigns to the app, or both. Every replay and purge is written to the dashboard log with the user's identity (OIDC) or `token-user` (token mode).

> **Note:** "Purge all" on the Dead letters page does the same as `orbit dlq purge`. It deletes every DLQ entry for good, including entries for failed flow steps, and those runs then stay `failed`. See [Error handling in flows](flows-error-handling.md).

## Running the dashboard in production

- Run it as its own process or container. Do not run it inside a worker. It is lightweight: about 60 MB RSS and almost no CPU when idle.
- It uses a small, fixed number of broker connections, independent of how many browser tabs are open. On Redis that is about 4 connections.
- Put it behind TLS. If a reverse proxy terminates TLS, read the `X-Forwarded-Proto` section of [Dashboard OIDC sign-in](dashboard-auth-oidc.md#reverse-proxies-and-redirect-loops) **before** you turn on OIDC.
- Container and Kubernetes examples: [Docker](deployment-docker.md), [Kubernetes](deployment-kubernetes.md).

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Queues page is empty but jobs are running | The dashboard's `orbit.toml` points at a different broker or Redis database |
| Flows page missing | `[results] backend = "none"` |
| Signed out after every deploy | Token mode. The token changes on restart |
| Endless redirects after IdP sign-in | Proxy is not sending `X-Forwarded-Proto`; see [OIDC](dashboard-auth-oidc.md) |
| Dashboard exits at startup with `ORB-1702` | OIDC keys are missing or the issuer cannot be reached |

For broker connection errors (`ORB-1001`, `ORB-1002`), see [Troubleshooting the broker](troubleshooting-broker.md).
