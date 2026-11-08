---
id: security
title: Security
section: Operations
applies_to: "3.x"
updated: 2026-10-30
---

# Security

This page covers how to report a vulnerability, which versions get security fixes, and how to
run Orbit 3.x safely in production.

## Reporting a vulnerability

Please **do not** open a public issue. Email **security@example.com** with a description,
affected versions, and a proof of concept if you have one. A maintainer acknowledges reports
within three working days and coordinates a fix and a disclosure date with you. We credit
reporters in the [changelog](changelog.md) unless you ask us not to.

## Supported versions

| Version | Security fixes |
|---|---|
| 3.2.x (current: 3.2.1) | Yes |
| 3.1.x | Critical fixes only, until the next minor release |
| 3.0.x | No. Upgrade to 3.2.x |
| 2.9.x | Yes, until end of life on **2026-12-31** |
| 2.8.x and earlier | No |

2.9.0 is the last 2.x release. After 2026-12-31 the 2.x line gets no fixes of any kind. Plan
the move with [migrating-2-to-3.md](migrating-2-to-3.md).

## Threat model in one paragraph

Orbit trusts its broker. Anyone who can write to the broker can enqueue any registered job with
any arguments, and those jobs run with your workers' privileges. Anyone who can read the broker,
the result backend or the dashboard can see job arguments and return values. Most of the advice
below follows from those two facts.

## Protect the broker

- **Use TLS and authentication.** For Redis, use a `rediss://` URL with a password or ACL user.
  For Postgres, require `sslmode=require` or stricter. For SQS, use IAM roles rather than static
  keys. A wrong credential shows up as `BrokerAuthError` (ORB-1002).
- **Isolate the network.** The broker should be reachable from producers and workers only.
- **Separate environments.** Never point staging workers at a production broker, even
  read-only.

## Keep secrets out of `orbit.toml` and out of git

`orbit.toml` usually contains the broker URL, and that often includes a password. Keep it out
of version control, render it at deploy time from your secrets manager, and make it readable
only by the worker user (`chmod 600`). See [deployment-systemd.md](deployment-systemd.md).

Alternatively, read the URL yourself and pass it in code. An explicit `broker=` argument takes
precedence over `[broker] url` ([api-reference-orbit.md](api-reference-orbit.md)):

```python
import os
from orbit import Orbit

app = Orbit(broker=os.environ["ATLAS_BROKER_URL"])
```

## Don't put secrets or PII in job arguments

Job arguments are stored in plaintext in the broker. They are copied to the dead-letter queue
on `RetryExhausted` (ORB-1301), and they are **shown to every signed-in dashboard user** on the
job detail page. Return values sit in the result backend for `[results] ttl_days` (default 7).

```python
# Bad: an API key and an email address now live in the broker, DLQ and dashboard
notify.enqueue(email="dana@example.com", api_key="sk-test-FAKE-0000")

# Good: pass identifiers and look sensitive values up inside the job
notify.enqueue(user_id="u_42")
```

Orbit serializes arguments as JSON only. It never unpickles anything from the broker, so a
malicious payload can't execute code during deserialization. Unsupported types fail with
`SerializationError` (ORB-1201) instead of falling back to pickle.

## Secure the dashboard

The dashboard can replay and purge the DLQ, so treat it as an admin tool.

```toml
[dashboard]
auth = "oidc"
oidc_issuer = "https://idp.example.com/realms/eng"
oidc_client_id = "orbit-dashboard"
```

- Use `auth = "oidc"` for teams. `auth = "token"` is fine for a single operator.
- Serve it only behind a TLS-terminating reverse proxy. `orbit dashboard --port 7777` speaks
  plain HTTP.
- Failed logins log `DashboardAuthFailed` (ORB-1701). A bad issuer or client ID fails at
  startup with `OIDCMisconfigured` (ORB-1702).

> **Note:** On 3.2.0 and later, an OIDC login behind a reverse proxy can loop between the
> dashboard and your identity provider. This is an open issue. The workaround is to make the
> proxy send `X-Forwarded-Proto: https`. Details are in
> [dashboard-auth-oidc.md](dashboard-auth-oidc.md).

## Limit blast radius

- Keep `[limits] max_payload_kb` (default 512) as low as your jobs allow. It is your first
  defense against a producer, or an attacker, flooding the broker with huge payloads
  (`PayloadTooLarge`, ORB-1202).
- Run workers as an unprivileged user with a read-only filesystem where possible.
- Review what your OTLP exporter sends. Span attributes include job names and queue names, so
  route telemetry only to collectors you trust ([observability-tracing.md](observability-tracing.md)).

## Supply chain

Pin Orbit to an exact version in your lock file, install with hash checking, and read the
[changelog](changelog.md) before upgrading. Run `orbit doctor` after every upgrade to confirm the
broker, config and package versions agree.
