# Individual accounts and private teams

The login page supports the existing Privy React SDK or Dynamic.xyz's React
SDK. Configure one active provider with `GHOST_AUTH_PROVIDER=privy` or
`GHOST_AUTH_PROVIDER=dynamic`. Dynamic uses an embedded login widget; the
email/Google methods enabled in your environment are displayed. No wallet
connector is configured by Ghost Trials. FastAPI verifies signed tokens and
creates revocable, organization-scoped sessions. Client-supplied emails, roles
and organization IDs are never trusted.

## Configure Dynamic.xyz

1. Create a Dynamic environment in the [Dynamic dashboard](https://app.dynamic.xyz/)
   and copy its public environment UUID. Enable email, Google and passkey sign-in there.
   Google may require OAuth configuration in Google Cloud before it appears.
2. Add the exact HTTPS frontend origin to Dynamic's allowed origins. Configure
   the JWT audience to that same origin, for example
   `https://ghosttrials.site`.
3. On the backend set `GHOST_AUTH_PROVIDER=dynamic`, `DYNAMIC_ENVIRONMENT_ID`,
   `DYNAMIC_JWT_AUDIENCE`, `GHOST_CUSTOMER_AUTH_REQUIRED=true`,
   `GHOST_PUBLIC_DEPLOYMENT=true`, `GHOST_COOKIE_SECURE=true`, and
   `GHOST_ALLOWED_ORIGINS` with that exact frontend origin. No Dynamic API token
   is needed for this sign-in path; never put one in frontend code.
4. Build the login assets with `npm ci` and `npm run build:auth`, then start the
   CPU backend. Test a real sign-in on the final HTTPS domain before public use.

The Dynamic sign-in page exposes a dedicated **Sign in with passkey** action.
After email/Google sign-in it holds on the account step so the user can choose
**Create passkey for this account** before opening the workspace. The passkey
ceremonies are performed by Dynamic's SDK; Ghost Trials receives only its JWT,
not the passkey private key. Configure passkeys for the Dynamic environment in
its dashboard and test on the final HTTPS domain. An embedded-wallet passkey is
not automatically an account sign-in passkey.

The API retrieves Dynamic's RS256 signing keys from a fixed provider JWKS URL,
then checks signature, environment ID, issuer, audience, issue/expiry times,
subject and any `requiresAdditionalAuth` scope. Provider/JWKS failure rejects
the login. Automated tests use locally generated signed tokens; they do **not**
prove your Dynamic dashboard or Google configuration works.

## Configure Privy (existing deployments)

The Privy path uses email, Google and passkeys when those methods are enabled
for the app. It does not create wallets, and verifies
ES256 signatures, issuer, audience, expiry, issued-at and subject using your
app's public Privy HTTPS JWKS endpoint. An optional pinned public PEM is
supported. An app secret is not needed for this flow.

## Configure Privy

1. Open your app in [Privy Dashboard](https://dashboard.privy.io/).
2. Enable Email, Google and Passkey in login-method settings. If new users should
   be able to create an account with a passkey directly, also enable passkey
   signup. Complete any Google OAuth setup prompted by Privy. A frontend button
   cannot activate a dashboard method.
3. Set allowed domains/origins to your actual frontend/backend HTTPS origins.
   Temporarily include the phone-preview origin, then remove it after moving to
   a permanent domain. Do not leave production origins unrestricted.
4. Set backend `GHOST_AUTH_PROVIDER=privy` and `PRIVY_APP_ID`; `PRIVY_CLIENT_ID` is optional. Keep any app secret
   private. Set `GHOST_CUSTOMER_AUTH_REQUIRED=true`, `GHOST_COOKIE_SECURE=true`
   and exact HTTPS origins in `GHOST_ALLOWED_ORIGINS`.
5. Run `npm ci`, `npm run build:auth`, and start exactly one API worker.

The page shows only login methods that Privy currently reports as enabled.
Existing email/Google users should sign in first and use **Create a passkey for
this account** so they retain the same workspace; the Account page links back
to sign-in, where a passkey action appears only if the provider enables it. Creating a new passkey
account can create a separate identity. Public login settings are
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
sign in through the configured provider, accept the invitation and enter the invited workspace.

The **Account** page is available from the workspace avatar and sidebar. It
shows the provider-backed identity, active workspace, role and sign-out action.
Individually signed-in users can edit their display name through authenticated
`PATCH /account`; the update is audited and visible to members of their
workspaces. It does not change their provider identity, email or login method.
Shared deployment tokens and unauthenticated local development sessions cannot
edit a profile.

Trials, scores, benchmarks, comparisons, replay/cancel, previews, videos, traces
and live events are filtered by active organization. Foreign IDs return 404.
Membership roles are reloaded for every request; removed members lose sessions
and live subscriptions. Cookies are opaque, HttpOnly, Secure, SameSite=Lax and
stored only as hashes. Logout revokes the server-side session, including stolen
copies. Session lifetimes never exceed the verified identity token's expiry.
Expired sessions redirect to the configured login provider.

Accounts store a provider-scoped user ID and generic display name, not an unverified
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
backups and the evidence from whichever CPU or GPU simulator is actually used
before onboarding paying customers.
