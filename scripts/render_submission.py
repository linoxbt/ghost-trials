"""Render the root Devpost dossier to a print-ready PDF.

Run: uv run --no-project --with markdown python scripts/render_submission.py
Requires a local Chromium or Google Chrome binary; no app credentials are read.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import shutil
import subprocess
import tempfile

import markdown


ROOT = Path(__file__).resolve().parents[1]
CSS = """
@page { size: A4; margin: 18mm 17mm 17mm; }
@page :first { margin: 0; }
* { box-sizing: border-box; }
html { color: #1d2027; background: white; }
body { margin: 0; font: 10.3pt/1.48 Arial, Helvetica, sans-serif; }
.cover { height: 297mm; padding: 28mm 24mm; background: #171b24; color: white;
         page-break-after: always; position: relative; }
.brand { color: #ff813f; font-size: 13pt; font-weight: 800; letter-spacing: .16em; }
.cover-rule { width: 29mm; height: 2.5mm; background: #ff813f; margin: 39mm 0 13mm; }
.cover h1 { font-size: 42pt; line-height: 1.02; letter-spacing: -.045em; margin: 0; color: white; }
.cover h2 { font-size: 17pt; line-height: 1.35; font-weight: 400; color: #e7e2df;
            max-width: 120mm; margin: 10mm 0; border: 0; }
.cover .meta { position: absolute; bottom: 25mm; left: 24mm; right: 24mm;
               border-top: 1px solid #5c6070; padding-top: 7mm; color: #d3d4d9; }
.cover .disclaimer { font-size: 9pt; color: #aeb0b9; margin-top: 5mm; }
main { padding: 0; }
main > h1:first-child { display: none; }
h1, h2, h3 { break-after: avoid; color: #181c25; }
h2 { font-size: 20pt; line-height: 1.16; margin: 13mm 0 4mm; border-bottom: 2px solid #f36c2a;
     padding-bottom: 2.5mm; }
h3 { font-size: 12.5pt; margin: 7mm 0 2mm; color: #a94218; }
p { margin: 0 0 3mm; orphans: 3; widows: 3; }
blockquote { margin: 4mm 0 7mm; padding: 2mm 4mm; border-left: 3px solid #f36c2a;
             background: #fff6f0; color: #4b403b; }
blockquote p { margin: 0; }
a { color: #aa4217; text-decoration: none; overflow-wrap: anywhere; }
strong { color: #161922; }
code { font: 8.7pt/1.4 'DejaVu Sans Mono', Consolas, monospace; background: #f1f2f4;
       padding: 0 .6mm; overflow-wrap: anywhere; }
pre { background: #f1f2f4; padding: 3mm; white-space: pre-wrap; }
ul, ol { margin: 2mm 0 4mm; padding-left: 6mm; }
li { margin: 1mm 0; }
table { width: 100%; border-collapse: collapse; margin: 4mm 0 6mm; font-size: 8.8pt; }
th { text-align: left; background: #1f2630; color: white; }
td, th { padding: 2mm 2.4mm; border: 1px solid #d6d8dd; vertical-align: top; }
tr { break-inside: avoid; }
thead { display: table-header-group; }
hr { border: 0; border-top: 1px solid #d7d9de; margin: 6mm 0; }
@media print { body { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
               h2, h3, blockquote, table { break-inside: avoid-page; } }
"""


def render(source: Path, output: Path) -> None:
    browser = shutil.which("google-chrome") or shutil.which("chromium")
    if not browser:
        raise RuntimeError("Chromium or Google Chrome is required to render the submission PDF")
    if not source.is_file():
        raise FileNotFoundError(source)
    full_text = source.read_text(encoding="utf-8")
    story = full_text.split("## Project story — paste into “About the project”", 1)[1].split(
        "## Additional-info answers — paste field by field", 1)[0]
    evidence = full_text.split("## Evidence and reproducibility notes for judges", 1)[1].split(
        "## Final owner checklist", 1)[0]
    judge_text = """## System and evidence at a glance

| Capability | Demonstrated status |
| --- | --- |
| Robot simulation | Real headless MuJoCo gantry-arm manipulation on CPU |
| Autonomous search | Bounded adaptive trials, reproduction, mutation, empirical boundary and regression |
| Evidence | Telemetry, recipe, seed, controller digest, simulator version and independently recomputed trace metrics |
| Local agent domain | Bundled executable reference agent, mock tools, versioned assertions, verified failure replay and case-specific regression; not deployed or open to arbitrary code |
| NVIDIA / Nebius | One completed live Nemotron 3 Super review of a verified MuJoCo trial through Token Factory |
| Not demonstrated | Physical robot, G1/SONIC/GR00T worker, live Cosmos generation, Nebius AI Cloud GPU or safety certification |

**Live application:** https://ghosttrials.site/

**Public source and MIT license:** https://github.com/linoxbt/ghost-trials

**Scope:** an experimental policy-failure discovery platform, not a certified robot-safety assessment.

## Why Ghost Trials exists and how it works
""" + story + "\n## Evidence and reproducibility notes for judges\n" + evidence
    body = markdown.markdown(judge_text, extensions=["tables", "fenced_code", "sane_lists"])
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
    <title>Ghost Trials — Devpost submission dossier</title><style>{CSS}</style></head><body>
    <section class="cover"><div class="brand">GHOST TRIALS</div><div class="cover-rule"></div>
    <h1>Evidence before<br>confidence.</h1>
    <h2>Autonomous failure discovery for executable physical-AI controllers, with a controlled agent-verification extension</h2>
    <div class="meta">Nebius x NVIDIA Global AI Hackathon · Physical AI Track<br>
    Updated 20 October 2026<br><div class="disclaimer">Experimental evaluation platform — not a safety certification. Agent domain is local, not yet deployed.</div></div>
    </section><main>{body}</main></body></html>"""
    output = output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ghost-submission-render-") as directory:
        html_file = Path(directory) / "submission.html"
        html_file.write_text(document, encoding="utf-8")
        subprocess.run([browser, "--headless", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", f"--print-to-pdf={output}",
                        html_file.as_uri()], check=True, capture_output=True, text=True)
    if not output.is_file() or output.stat().st_size < 10_000:
        raise RuntimeError("PDF was not generated or is unexpectedly small")
    print(f"Rendered {html.escape(str(output))} ({output.stat().st_size} bytes)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "submission.md")
    parser.add_argument("--output", type=Path, default=ROOT / "submission.pdf")
    args = parser.parse_args()
    render(args.source, args.output)


if __name__ == "__main__":
    main()
