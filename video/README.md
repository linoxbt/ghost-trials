# Ghost Trials film

Original Remotion source for the [Ghost Trials film](ghost-trials-1080p.mp4). The narration is locked in [`script.json`](script.json), and scene duration comes from generated [`src/timing.json`](src/timing.json). The picture uses the site's own logo and app palette, code drawn interface visualizations, a labeled conceptual tabletop diagram, timed captions, and a single 1080p render worker. The interface and tabletop views are labeled in the picture; they are not trial recordings or executed results.

```bash
cd video
npm ci
npm run finish
npm run draft
npm run render
npm run final
npm run poster
```

`finish` validates factual values against the parent repository's `README.md` and `docs/HUNT.md`, resolves the narrator, generates voice and music if available, builds word timing, captures the public site, and prepares visual crops. Put an ElevenLabs key in `video/.env` to generate new audio. The supplied audio and alignment assets keep the published cut reproducible without a key. If the paid Music API returns 402, the music job can assemble a quiet score from sound generation. A 401 or unavailable audio endpoint is skipped without stopping the film.

The sound design normalizes the music and selected effects, then places each cue on a visible action. `npm run final` measures the master and writes a broadcast copy when the mix needs loudness correction; the original render remains available.

The default render is 1920×1080 at 30 fps, H.264/AAC, concurrency 1. The 4K job runs only when `FINAL_4K=1`. No desktop or interactive browser is needed. This film describes CPU simulation evidence and does not claim a GPU demonstration or safety certification.
