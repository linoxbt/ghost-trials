# Individual accounts and private teams

The login page uses the official Privy React SDK with email and Google only.
It does not create wallets. FastAPI verifies ES256 signatures, issuer, audience,
expiry, issued-at and subject using your app's public Privy HTTPS JWKS endpoint.
An optional pinned public PEM is supported. An app secret is not needed for this
flow. Client-supplied emails, roles and organization IDs are never trusted.

## Configure Privy

1. Open your app in [Privy Dashboard](https://dashboard.privy.io/).
2. Enable Email and Google in login-method settings. Complete any Google OAuth
   setup prompted by Privy. A frontend button cannot activate a dashboard method.
3. Set allowed domains/origins to your actual frontend/backend HTTPS origins.
   Temporarily include the phone-preview origin, then remove it after moving to
   a permanent domain. Do not leave production origins unrestricted.
4. Set backend `PRIVY_APP_ID`; `PRIVY_CLIENT_ID` is optional. Keep any app secret
   private. Set `GHOST_CUSTOMER_AUTH_REQUIRED=true`, `GHOST_COOKIE_SECURE=true`
   and exact HTTPS origins in `GHOST_ALLOWED_ORIGINS`.
5. Run `npm ci`, `npm run build:auth`, and start exactly one API worker.

The page checks which login methods Privy actually enables. Google disabled in
the dashboard is displayed as awaiting activation. Public login settings are
cached for one minute, verification keys for five. Provider/key failures reject
verification rather than accepting unsigned tokens. Plain HTTP localhost needs
secure cookies disabled for local development only; the HTTPS phone preview
keeps them enabled. Mutating cookie requests and WebSockets check exact origins.

## Account and workspace boundaries

A first verified sign-in creates a personal workspace and owner/admin membership
on the server. Existing records belong to `legacy` and are accessible only with
private deployment role credentials, not automatically to new customers. A
customer admin does not gain global operations access.

In **Team & access**, accounts can create up to five owned workspaces, switch
memberships, inspect their admission budget and see team members. Admins create
single-use 24-hour invitation links for viewer/operator membership, edit roles,
remove members and inspect individual audit history. The owner cannot be removed
or demoted. Existing membership roles are never changed by invitation replay.
Invitations are bearer links: share them privately with the intended teammate.
The app does not email invitations or bind a link to an email address. Recipients
sign in through Privy, accept the invitation and enter the invited workspace.

Trials, scores, benchmarks, comparisons, replay/cancel, previews, videos, traces
and live events are filtered by active organization. Foreign IDs return 404.
Membership roles are reloaded for every request; removed members lose sessions
and live subscriptions. Cookies are opaque, HttpOnly, Secure, SameSite=Lax and
stored only as hashes. Logout revokes the server-side session, including stolen
copies. Session lifetimes never exceed the verified identity token's expiry.
Expired sessions redirect to login; Privy refreshes identity credentials there.

Accounts store an opaque Privy DID and generic display name, not an unverified
frontend email/Google profile. `GHOST_PUBLIC_SIGNUP_ENABLED=false` rejects new
app accounts: use only after onboarding members, since invitations do not bypass
this restriction. Signup can remain enabled while team records stay private and
new workspaces have zero paid execution budget.

## Deployment and budgets

```bash
uv run python -m ghost_trials.private_setup --privy-app-id YOUR_PUBLIC_ID --domain your-domain.example --email operator@example.com
```

This prepares owner-only access/config files without overwriting existing ones,
buying compute or claiming real execution. Review configuration and permanent
DNS, then start `deployment/secure.compose.yaml`; see
[PRODUCTION_READINESS.md](PRODUCTION_READINESS.md). Keep bootstrap credentials
exclusively with platform operators.

Before live submissions, set positive platform/per-job reservation ceilings,
confirm external provider spending controls and allocate each organization's
budget through platform-only `PUT /ops/organizations/{id}/budget` with
`{"limit_cents": 500}`. Reservations are atomic with queue acceptance and persist
across restarts. No automatic refunds follow failures because providers may have
already charged. These are **not measured usage billing, customer payments or
guaranteed caps on GPU/endpoint charges**.

Isolation is application-enforced in one SQLite-backed API process, not Postgres
RLS or an independently audited enterprise deployment. Do not enable multiple
replicas. Verify genuine provider sign-in, production DNS, security/load behavior,
backups and real GPU evidence before onboarding paying customers.
