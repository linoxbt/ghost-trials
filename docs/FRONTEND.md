# Ghost Trials workspace

FastAPI serves the animated landing page at `/`, documentation at `/docs`, and the application at `/app/`. The API explorer is `/api/docs`. Application navigation uses hash URLs under `/app/`; legacy links such as `/#/overview` redirect to `/app/#/overview`.

| URL | Workspace |
| --- | --- |
| `/#/overview` | Experimental evaluation index, outcome distribution, configured pipeline, recent runs |
| `/#/hunt` | Release the Ghost: executable G1 task, pinned checkpoint, bounded budget and hazard family |
| `/#/hunt/<hunt_id>` | Live candidate sequence, search map, evidence status and verified case links |
| `/#/failures` | Verified Ghost Case library; synthetic outcomes are excluded |
| `/#/failures/<case_id>` | Recording, measured observations, verification, interpretation and checkpoint comparisons |
| `/#/trials` | Search and filter trials by outcome and severity |
| `/#/trials/<trial_id>` | Flight record, preview, policy recording, metrics, finding, JSON export |
| `/#/scenarios` | Supported hazard templates and evaluated scenarios |
| `/#/new` | Trial creation, optional seed, severity, inline submission errors |
| `/#/reports` | Completed records, evaluation export, scoring rubric |
| `/#/system` | Server-reported provider configuration and Advanced/Labs links to physical capture, benchmarks and manual trials |

The desktop navigation can be collapsed using the hamburger button. Below 900px it becomes a drawer with an overlay, focus containment, Escape to close, and focus restoration. Below 620px, ledgers become stacked records with labeled measurements and full-width review/export actions. Form controls use 16px text to avoid automatic zoom on iPhones. Form inputs and stable trial media are retained during background refreshes. WebSocket updates reconnect automatically; polling also refreshes the data every 20 seconds.

The System page reports configuration, not GPU readiness. The development banner labels synthetic data. Reports export existing records and artifact links; they do not download or bundle remote videos.

The Hunt, trial creation and System views use `/capabilities` to explain expected outputs and missing generation configuration. Hunt task and environment fields are pinned to what the configured worker actually executes; arbitrary user text is not passed off as a robot task. In local mode Hunts and manual trials are explicitly synthetic demonstrations, without claiming that Cosmos or Isaac executed. The old emoji preview was replaced by a labeled SVG development schematic. See [Hunt architecture](HUNT.md).

The landing page uses a responsive canvas technical scene, hazard switching, play/pause controls, scroll reveals, and CSS diagrams. Animations respect reduced-motion preferences; the canvas pauses when hidden or outside the viewport. The docs include topic search, section navigation, and copyable examples. `scripts/check_public_site.cjs` checks these public-page interactions.

## Visual identity

The custom **Sentinel mark** combines a protective shield, ghost silhouette, and precision-cut G. The standalone SVG scales to sidebar and favicon sizes. The full logo adds a wordmark and Physical AI Safety descriptor.

- Symbol: `static/ghost-mark.svg`
- Full logo on a light background: `static/ghost-logo.svg`
- Brand orange: `#F36B2B`
- Interface orange: `#ED6225`; solid buttons use `#C64B16` for white text contrast
- Charcoal: `#191B1E`
- Canvas: `#F7F6F3`
- Typography: DM Sans and IBM Plex Mono, with local system fallbacks

Outcome colors retain their meaning: green for avoided, amber for mitigated, red for failed, purple for catastrophic.

## Verification

Start the development app with `make dev`. Run `node scripts/check_frontend.cjs` with Playwright available. If it is installed elsewhere, set `PLAYWRIGHT_MODULE` to its package path. Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE` if using an existing browser binary, and optionally `GHOST_PREVIEW_URL` for a different local port.

The check refuses production mode, creates one synthetic trial, verifies filtering, creation, navigation, downloads, form preservation, provider errors, mobile menu behavior and responsive widths. It saves review screenshots under `/tmp/ghost-*.png`.
