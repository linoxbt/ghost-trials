"""Private local evidence retention with an optional content-addressed S3 replica."""
import asyncio
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def origin(url):
    value = urlsplit(url)
    if value.scheme not in {"https", "http"} or not value.hostname or value.username or value.password:
        raise ValueError("Unsafe artifact origin")
    return value.scheme, value.hostname, value.port or (443 if value.scheme == "https" else 80)


class EvidenceRepository:
    def __init__(self, settings, transport=None, s3=None):
        self.settings, self.transport, self.s3 = settings, transport, s3

    def replicate(self, path: Path):
        if not self.settings.ghost_artifact_bucket:
            return None
        if self.s3 is None:
            import boto3
            self.s3 = boto3.client("s3", endpoint_url=self.settings.ghost_s3_endpoint,
                                   region_name=self.settings.ghost_s3_region)
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        key = f"sha256/{digest}/{path.name}"
        # Credentials use the SDK chain. No public ACL or public artifact URL.
        with path.open("rb") as stream:
            self.s3.put_object(Bucket=self.settings.ghost_artifact_bucket, Key=key,
                Body=stream, Metadata={"sha256": digest}, ServerSideEncryption="AES256")
        return {"key": key, "sha256": digest}

    async def capture(self, trial, scenario, result):
        manifest = result.get("artifacts", {})
        if set(manifest) != {"simulation.mp4", "telemetry.jsonl", "recipe.json"}:
            raise ValueError("Required worker evidence missing")
        total = 0
        for name, record in manifest.items():
            if type(record.get("bytes")) is not int or record["bytes"] <= 0:
                raise ValueError("Invalid artifact size")
            total += record["bytes"]
        if total > 1_000_000_000:
            raise ValueError("Evidence exceeds storage bounds")
        directory = self.settings.ghost_artifact_root / "trials" / trial.trial_id
        directory.mkdir(parents=True, exist_ok=False)
        replicas = {}
        async with httpx.AsyncClient(timeout=120, follow_redirects=False, transport=self.transport) as client:
            for name, record in manifest.items():
                url = result.get("artifact_urls", {}).get(name)
                if not url or origin(url) != origin(self.settings.isaac_job_endpoint):
                    raise ValueError("Artifact origin differs from trusted worker")
                count, digest = 0, hashlib.sha256()
                async with client.stream("GET", url) as response:
                    response.raise_for_status()
                    with (directory / name).open("xb") as output:
                        async for chunk in response.aiter_bytes():
                            count += len(chunk)
                            if count > record["bytes"]:
                                raise ValueError("Artifact exceeds declared size")
                            digest.update(chunk)
                            output.write(chunk)
                if count != record["bytes"] or digest.hexdigest() != record["sha256"]:
                    raise ValueError("Worker artifact integrity mismatch")
        # Verification is mandatory before scoring. Video decoding is a separate release gate.
        metrics = trial.metrics.model_dump(mode="json")
        metrics.update(simulation_video_url="simulation.mp4", trace_url="telemetry.jsonl")
        (directory / "result.json").write_text(json.dumps({"metrics": metrics, "artifacts": manifest}))
        (directory / "scenario.json").write_text(scenario.model_dump_json())
        from .independent_validation import verify_bundle
        verification = verify_bundle(directory, self.settings.gr00t_checkpoint_digest)
        from .release_gate import decode_video
        await asyncio.to_thread(decode_video, directory / "simulation.mp4")
        verification["video_decoded"] = True
        (directory / "verification.json").write_text(json.dumps(verification))
        for path in directory.iterdir():
            replica = await asyncio.to_thread(self.replicate, path)
            if replica:
                replicas[path.name] = replica
        if scenario.video_url and scenario.video_url.startswith("/generated/"):
            cosmos = self.settings.ghost_artifact_root / scenario.scenario_id / "cosmos.mp4"
            replica = await asyncio.to_thread(self.replicate, cosmos)
            if replica:
                replicas["cosmos.mp4"] = replica
        if replicas:
            (directory / "replicas.json").write_text(json.dumps(replicas))
        trial.metrics.simulation_video_url = f"/generated/trials/{trial.trial_id}/simulation.mp4"
        trial.metrics.trace_url = f"/generated/trials/{trial.trial_id}/telemetry.jsonl"
        return verification
