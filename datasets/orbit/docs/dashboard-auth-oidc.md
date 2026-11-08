---
id: dashboard-auth-oidc
title: Dashboard OIDC sign-in
section: Dashboard
applies_to: "3.x"
updated: 2026-10-28
---

# Dashboard OIDC sign-in

With OIDC, people sign in to the [dashboard](dashboard.md) with your company identity provider (IdP) instead of the random startup token. Choose OIDC for shared dashboards, multiple replicas, or sign-ins tied to a named user.

## How it works

The dashboard is an OIDC **public client**. It uses the authorization code flow with **PKCE** and **does not need a client secret**, so `orbit.toml` contains no IdP secret at all. Only two settings are needed:

```toml
[dashboard]
auth = "oidc"
oidc_issuer = "https://login.example.com/"
oidc_client_id = "orbit-dashboard"
```

At startup the dashboard fetches `<oidc_issuer>/.well-known/openid-configuration` and the IdP's signing keys. When a user signs in, it validates the ID token: signature, `iss`, `aud` (must equal `oidc_client_id`) and expiry. It then creates a session. Sessions are stored **in the broker**, so they survive restarts and work on every replica.

## Register the dashboard with your IdP

Settings you will need in your IdP (the exact labels differ between providers):

| Setting | Value |
|---|---|
| Application type | Public client / SPA / "native", with PKCE required |
| Redirect (callback) URI | `https://orbit.example.com/auth/callback` |
| Post-logout redirect URI | `https://orbit.example.com/` |
| Scopes | `openid profile email` |
| Grant type | Authorization code |

The callback path is always `/auth/callback`. The scheme and host are taken from the incoming request, which matters behind a proxy (see below). For local testing, register `http://localhost:7777/auth/callback` as well.

> **Note:** Orbit does not check groups or roles. **Anyone your IdP lets sign in to this client gets full dashboard access**, including DLQ replay and purge. Control access in the IdP by assigning the application only to the right group.

## Startup checks and ORB-1702

The dashboard refuses to start, and logs **`ORB-1702 OIDCMisconfigured`**, when:

- `oidc_issuer` or `oidc_client_id` is missing,
- the discovery document cannot be fetched (DNS, TLS or firewall problem), or
- the `issuer` value in the discovery document does not **exactly** match `oidc_issuer`.

Watch the trailing slash: copy the `issuer` value exactly from the discovery document:

```bash
curl -s https://login.example.com/.well-known/openid-configuration | python3 -c \
  'import json,sys; print(json.load(sys.stdin)["issuer"])'
```

## Sign-in failures and ORB-1701

When a sign-in reaches the callback but fails validation, the user sees "Sign-in failed" and the log gets **`ORB-1701 DashboardAuthFailed`** with a reason:

| Reason in log | Meaning | Fix |
|---|---|---|
| `aud mismatch` | The token was issued for another client | Check `oidc_client_id` |
| `token expired` / `iat in future` | The dashboard host's clock is off | Run NTP on the host. Allowed skew is 60 s |
| `state mismatch` | The state cookie was lost between login and callback | Usually a proxy scheme problem; see below |
| `pkce verification failed` | The IdP is not set up for PKCE | Mark the client as public / PKCE required |

## Reverse proxies and redirect loops

> **Note:** **Known issue in 3.2.0, still open.** If TLS is terminated at a reverse proxy, the dashboard can fall into an **endless redirect loop** after the IdP sign-in. **Workaround:** make sure the proxy sends `X-Forwarded-Proto: https` to the dashboard.

Why it loops: the dashboard sees a plain-HTTP request from the proxy. It builds an `http://` callback URL and sets its state cookie without the `Secure` flag. The browser comes back on `https://`, the proxy redirects `http` to `https` again, the state check fails, and the dashboard starts a new sign-in. This repeats forever. Some browsers stop after about 20 redirects with `ERR_TOO_MANY_REDIRECTS`. The log shows a run of `ORB-1701 ... state mismatch` lines.

When the dashboard receives `X-Forwarded-Proto`, it uses that scheme for the callback and the cookie.

**nginx**

```nginx
location / {
    proxy_pass http://127.0.0.1:7777;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto https;
}
```

Use the literal value `https` here. Do not use `$scheme`: when nginx itself sits behind a load balancer that terminates TLS, `$scheme` is `http`, and you get the loop again.

**Kubernetes ingress-nginx** sets `X-Forwarded-Proto` for you. If another load balancer that terminates TLS sits in front of the ingress controller, also enable `use-forwarded-headers: "true"` in the controller ConfigMap so that the original scheme is passed through. See [Kubernetes deployment](deployment-kubernetes.md).

**AWS ALB** sends `X-Forwarded-Proto` by default. The loop only appears if a sidecar proxy in between overwrites it.

To confirm the header reaches the dashboard, open `https://orbit.example.com/auth/debug` while signed out. It shows the scheme, host and callback URL that the dashboard derived from the request.

## Sessions and sign-out

- A session lasts as long as the IdP's ID token, and is then renewed by a new redirect to the IdP. If the user still has an IdP session, the redirect is invisible.
- **Sign out** removes the dashboard session and redirects to the IdP's end-session endpoint, if the IdP publishes one.
- Removing a user from the IdP application stops them signing in again, but **does not end a session they already have**. That session lasts until their current token expires. To force everyone out at once, delete the `orbit:dashboard:session:*` keys (Redis) or truncate `orbit_dashboard_sessions` (Postgres).

## Switching from token mode

1. Register the client and set the three `[dashboard]` keys.
2. Run `orbit doctor` to catch typos (`ORB-1802 UnknownConfigKey`).
3. Restart the dashboard. Token sign-in URLs stop working straight away.

See also: [Security](security.md) and [Configuration reference](configuration-reference.md#dashboard).
