"""Prepare local credentials and statically inspect GR00T checkpoint packages.

This does not create provider-issued credentials, rent GPUs, train weights, or
claim that a checkpoint has passed inference. Nothing changes the live .env.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import secrets
import shlex
import subprocess


def private_create(path: Path, value: str) -> None:
    """Create secrets exclusively, without replacing existing user files."""
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as stream:
        stream.write(value)


def prepare(root: Path, output: Path) -> dict:
    if output.is_symlink():
        raise ValueError("Credential directory must not be a symlink")
    output.mkdir(parents=True, exist_ok=True, mode=0o700)
    output.chmod(0o700)
    secret_file = output / "credentials.json"
    if not secret_file.exists():
        private_create(secret_file, json.dumps({"worker_token": secrets.token_urlsafe(48)}, indent=2)+"\n")
    if secret_file.is_symlink():
        raise ValueError("Credential file must not be a symlink")
    secret_file.chmod(0o600)
    token = json.loads(secret_file.read_text())["worker_token"]
    if not isinstance(token, str) or len(token) < 32 or any(c.isspace() for c in token):
        raise ValueError("Invalid saved worker token; refusing to rotate it silently")
    runner = f"{root}/.venv/bin/python -m workers.isaac.trial_runner"
    worker_file = output / "worker.env"
    if not worker_file.exists():
        private_create(worker_file, "\n".join([
            f"ISAAC_WORKER_TOKEN={shlex.quote(token)}",
            "ISAAC_WORKER_BACKEND=gear_sonic_sim",
            "ISAAC_WORKER_REQUIRE_GPU=true",
            "ISAAC_WORKER_REQUIRE_POLICY=true",
            "ISAAC_WORKER_ALLOW_UNAUTHENTICATED=false",
            f"ISAAC_RUNNER_COMMAND={shlex.quote(runner)}",
            f"GEAR_SONIC_SIM_COMMAND={shlex.quote(f'bash {root}/scripts/run_sonic_trial.sh --request {{request}} --output {{output}}')}",
            "ISAAC_WORKER_PUBLIC_BASE_URL=http://127.0.0.1:9000",
            f"ISAAC_WORKER_OUTPUT_ROOT={shlex.quote(str(root / 'artifacts/worker'))}",
            "GR00T_POLICY_HOST=127.0.0.1", "GR00T_POLICY_PORT=5550",
            "GR00T_CHECKPOINT=", "GR00T_CHECKPOINT_DIGEST=", "",
        ]))
    production_file = output / "production.env"
    if not production_file.exists():
        template = (root / "deployment/production.env.example").read_text()
        replacements = {
            "ISAAC_JOB_TOKEN": token, "ISAAC_WORKER_TOKEN": token,
            "COSMOS_BASE_URL": "", "ISAAC_JOB_ENDPOINT": "",
            "GR00T_CHECKPOINT": "", "GR00T_CHECKPOINT_DIGEST": "",
        }
        lines=[]
        for line in template.splitlines():
            key=line.partition("=")[0]
            lines.append(f"{key}={shlex.quote(replacements[key])}" if key in replacements else line)
        private_create(production_file, "\n".join(lines)+"\n")
    key = output / "gpu_ed25519"
    if not key.exists():
        if key.with_suffix(".pub").exists():
            raise ValueError("Public SSH key exists without its private key; refusing replacement")
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "ghost-trials-gpu", "-f", str(key)], check=True)
    key.chmod(0o600)
    return {
        "worker_credentials": str(worker_file), "production_config": str(production_file),
        "ssh_public_key": str(key.with_suffix(".pub")),
        "provider_credentials_created": False, "gpu_provisioned": False,
        "checkpoint_created": False,
    }


def inspect_checkpoint(root: Path, tag: str = "unitree_g1_sonic", expected_digest: str | None = None) -> dict:
    root = root.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Checkpoint must be a directory")
    config = json.loads((root / "config.json").read_text())
    if not isinstance(config, dict) or not config:
        raise ValueError("Empty or invalid model config")
    processor = root if (root / "processor_config.json").exists() else root / "processor"
    pconfig = json.loads((processor / "processor_config.json").read_text())
    modalities = pconfig.get("processor_kwargs", {}).get("modality_configs", {})
    if tag not in modalities:
        raise ValueError(f"Checkpoint does not support {tag}; a base or different-embodiment model cannot be substituted")
    if tag == "unitree_g1_sonic":
        action_keys = modalities[tag].get("action", {}).get("modality_keys", [])
        if set(action_keys) != {"motion_token", "left_hand_joints", "right_hand_joints"}:
            raise ValueError("SONIC checkpoint must expose motion_token and both hand-joint actions")
    statistics = json.loads((processor / "statistics.json").read_text())
    if not isinstance(statistics, dict) or not statistics.get(tag):
        raise ValueError(f"Normalization statistics for {tag} are missing")
    index = root / "model.safetensors.index.json"
    if index.exists():
        mapping = json.loads(index.read_text()).get("weight_map", {})
        if not mapping:
            raise ValueError("Weight index is empty")
        names = sorted(set(mapping.values()))
    else:
        names = ["model.safetensors"]
    for name in names:
        if not isinstance(name, str) or Path(name).name != name:
            raise ValueError("Weight index references an unsafe path")
        path = root / name
        if not path.is_file() or path.stat().st_size < 16:
            raise ValueError(f"Missing or empty weight shard: {name}")
        with path.open("rb") as stream:
            length = int.from_bytes(stream.read(8), "little")
            if not 2 <= length <= min(100_000_000, path.stat().st_size-8):
                raise ValueError(f"Invalid safetensors header: {name}")
            header = json.loads(stream.read(length))
            if not isinstance(header, dict):
                raise ValueError(f"Invalid tensor header object: {name}")
            tensors = [v for k,v in header.items() if k != "__metadata__"]
            if not tensors or any(not isinstance(v, dict) or "data_offsets" not in v for v in tensors):
                raise ValueError(f"No tensor metadata in shard: {name}")
            data_size=path.stat().st_size-8-length
            for tensor in tensors:
                offsets=tensor["data_offsets"]
                if not isinstance(offsets, list) or len(offsets)!=2 or any(type(v) is not int for v in offsets) or not 0 <= offsets[0] <= offsets[1] <= data_size:
                    raise ValueError(f"Out-of-range tensor data in shard: {name}")
    # Hash relative paths and file contents, never directory location.
    manifest=[]
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        if path.is_symlink():
            raise ValueError("Materialize checkpoint symlinks before calculating its deployment digest")
        digest=hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda:stream.read(1024*1024),b""):
                digest.update(block)
        manifest.append(f"{digest.hexdigest()}  ./{path.relative_to(root).as_posix()}\n")
    digest="sha256:"+hashlib.sha256("".join(manifest).encode()).hexdigest()
    if expected_digest is not None and digest != expected_digest:
        raise ValueError("Checkpoint content does not match GR00T_CHECKPOINT_DIGEST")
    return {"checkpoint":str(root), "embodiment":tag, "checkpoint_digest":digest,
            "weight_shards":len(names), "status":"static_checks_passed", "gpu_inference_validated":False}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest="command", required=True)
    init=commands.add_parser("prepare")
    init.add_argument("--output", type=Path, default=Path("deployment/private"))
    verify=commands.add_parser("checkpoint")
    verify.add_argument("path", type=Path)
    verify.add_argument("--tag", default="unitree_g1_sonic")
    verify.add_argument("--digest-only", action="store_true")
    verify.add_argument("--expected-digest")
    args=parser.parse_args()
    try:
        if args.command=="prepare":
            result=prepare(Path(__file__).resolve().parent.parent,args.output.absolute())
        else:
            result=inspect_checkpoint(args.path,args.tag,args.expected_digest)
        print(result["checkpoint_digest"] if getattr(args,"digest_only",False) else json.dumps(result,indent=2))
    except (ValueError, OSError, KeyError, TypeError, subprocess.CalledProcessError) as exc:
        parser.exit(1,f"Setup failed: {exc}\n")


if __name__=="__main__":
    main()
