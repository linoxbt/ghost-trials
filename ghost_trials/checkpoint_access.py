"""Inspect a Hugging Face checkpoint at a pinned revision before downloading weights.

This verifies access and the saved modality contract; it cannot create a trained
policy or grant access to gated/private repositories. It never loads remote code.
"""
import argparse
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil

from dotenv import dotenv_values

from .execution_setup import inspect_checkpoint


def compatible_metadata(config, processor, statistics, tag):
    if not isinstance(config, dict) or not config:
        raise ValueError("Missing model config")
    modality = processor.get("processor_kwargs", {}).get("modality_configs", {}).get(tag)
    if not modality or not statistics.get(tag):
        raise ValueError(f"No compatible saved modalities and normalization for {tag}; do not substitute base/controller weights")
    if tag == "unitree_g1_sonic" and set(modality.get("action", {}).get("modality_keys", [])) != {"motion_token", "left_hand_joints", "right_hand_joints"}:
        raise ValueError("Checkpoint actions do not match the SONIC motion-token/hand interface")


def safe_prefix(value):
    path = PurePosixPath(value)
    if path.is_absolute() or ".." in path.parts or "\\" in value:
        raise ValueError("Unsafe checkpoint subfolder")
    return "" if str(path) == "." else str(path).rstrip("/") + "/"


def access(repo, revision="main", subfolder="", tag="unitree_g1_sonic", destination=None, max_bytes=0):
    from huggingface_hub import HfApi, hf_hub_download
    token = os.getenv("HF_TOKEN") or dotenv_values(".env").get("HF_TOKEN") or False
    api = HfApi(token=token)
    info = api.model_info(repo, revision=revision, files_metadata=True)
    if not re.fullmatch(r"[0-9a-f]{40}", info.sha or ""):
        raise ValueError("Model repository did not resolve to an immutable commit")
    prefix = safe_prefix(subfolder)
    files = {f.rfilename[len(prefix):]: f for f in info.siblings if f.rfilename.startswith(prefix)}
    processor = "processor/" if "processor/processor_config.json" in files else ""
    required = ["config.json", processor + "processor_config.json", processor + "statistics.json"]
    local = {}
    for name in required:
        if name not in files or files[name].size is None or files[name].size > 20_000_000:
            raise ValueError(f"Missing or oversized checkpoint metadata: {name}")
        local[name] = Path(hf_hub_download(repo, prefix + name, revision=info.sha, token=token))
    compatible_metadata(*(json.loads(local[name].read_text()) for name in required), tag)
    weights = [name for name in files if "/" not in name and name.endswith(".safetensors")]
    if not weights:
        raise ValueError("Compatible metadata exists but no safetensors weights are listed")
    selected = sorted(name for name in files if (name in required or name in weights or name == "model.safetensors.index.json"
                      or (".." not in PurePosixPath(name).parts and name.endswith((".json", ".txt", ".model")) and ("/" not in name or name.startswith(processor) and processor))))
    if any(files[name].size is None or files[name].size < 0 for name in selected):
        raise ValueError("Download sizes are unavailable; refusing an unbounded download")
    total = sum(files[name].size for name in selected)
    report = {"repo_id": repo, "revision": info.sha, "subfolder": subfolder, "embodiment": tag,
              "status": "metadata_compatible", "download_bytes": total, "gpu_inference_validated": False,
              "license": getattr(info.card_data, "license", None)}
    if destination:
        if max_bytes <= 0 or total > max_bytes:
            raise ValueError("Download exceeds the explicit byte budget; review metadata first")
        destination = Path(destination)
        destination.mkdir(parents=True, exist_ok=False)
        for name in selected:
            if PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts or "\\" in name:
                raise ValueError("Unsafe repository path")
            source = local.get(name) or Path(hf_hub_download(repo, prefix + name, revision=info.sha, token=token))
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)  # Materialized files, not cache symlinks.
        (destination / "ghost-source.json").write_text(json.dumps(report, indent=2))
        report.update(inspect_checkpoint(destination, tag))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--subfolder", default="")
    parser.add_argument("--tag", choices=["unitree_g1_sonic", "g1_wbc_joint"], default="unitree_g1_sonic")
    parser.add_argument("--download-to", type=Path)
    parser.add_argument("--max-download-gb", type=float, default=0)
    args = parser.parse_args()
    try:
        print(json.dumps(access(args.repo, args.revision, args.subfolder, args.tag, args.download_to,
                                int(args.max_download_gb * 1_000_000_000)), indent=2))
    except Exception as exc:
        # Hub exceptions can contain signed URLs. Only publish a safe category.
        print(json.dumps({"status": "blocked", "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, ValueError) else "Check repository access, accepted model terms, and the private HF_TOKEN"}))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
