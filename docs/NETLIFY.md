# Netlify frontend and FastAPI backend

Netlify serves the landing page, documentation, and workspace. The FastAPI service remains on the Ghost Trials host, where trial state and artifacts persist. Netlify's build creates 200 proxy rewrites for the JSON API and generated artifacts. The workspace polls for trial updates when served by Netlify.

Set one Netlify build variable: `GHOST_BACKEND_ORIGIN` = the public HTTPS origin of the running FastAPI service. The value must contain no path. The build fails if it is absent. Netlify does not need `NEBIUS_API_KEY`, Cosmos keys, checkpoint paths, or GPU worker tokens for this deployment; keep those on their respective backend services.

Build the Privy assets with `npm ci` and `npm run build:auth`, then build locally with `GHOST_BACKEND_ORIGIN=https://your-api.example python3 scripts/build_netlify.py`. The output is `netlify-dist/`. The Netlify site uses [netlify.toml](../netlify.toml) and publishes that directory. If the origin changes, update the Netlify variable and redeploy.

The current FastAPI host uses an automatically assigned Cloudflare quick tunnel URL. That URL can change when the tunnel is replaced. For a durable deployment, place the backend behind a stable HTTPS hostname, then update `GHOST_BACKEND_ORIGIN`. The public backend currently runs synthetic development adapters; GPU execution requires the separate resources listed in [GPU acceptance](GPU_ACCEPTANCE.md).

## Private API deployment

See [PRODUCTION_READINESS.md](PRODUCTION_READINESS.md) for permanent HTTPS hosting
and authenticated access. The Netlify builder now proxies `/account`, `/organizations`, `/organizations/*`, `/auth/*`, `/ops/*` and
`/ready` in addition to the trial/evidence routes. A temporary tunnel is not a
production backend, and this configuration does not resolve a Netlify usage limit.
