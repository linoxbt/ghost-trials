#!/usr/bin/env bash
set -euo pipefail

ROLE="${1:-}"
if [[ "$ROLE" != "cosmos" && "$ROLE" != "robotics" ]]; then
  echo "Usage: $0 cosmos|robotics" >&2
  exit 2
fi
if [[ "${EUID}" -ne 0 ]]; then
  echo "Run as root on the fresh Ubuntu GPU host." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
nvidia-smi >/dev/null
apt-get update
apt-get install -y --no-install-recommends ca-certificates curl git git-lfs jq openssl python3-pip rsync gnupg

if ! command -v docker >/dev/null; then
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  . /etc/os-release
  printf 'Types: deb\nURIs: https://download.docker.com/linux/ubuntu\nSuites: %s\nComponents: stable\nArchitectures: amd64\nSigned-By: /etc/apt/keyrings/docker.asc\n' "$VERSION_CODENAME" > /etc/apt/sources.list.d/docker.sources
  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
fi

if ! command -v nvidia-ctk >/dev/null; then
  curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey |
    gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list |
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
      > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  apt-get update
  apt-get install -y nvidia-container-toolkit
  nvidia-ctk runtime configure --runtime=docker
  systemctl restart docker
fi

nvidia-smi >/dev/null
docker run --rm --gpus all nvidia/cuda:12.8.0-base-ubuntu22.04 nvidia-smi >/dev/null
install -d -m 0750 /etc/ghost-trials /var/lib/ghost-trials

if [[ "$ROLE" == "cosmos" ]]; then
  install -d -m 0770 /var/lib/ghost-trials/nim-cache
else
  install -d -m 0770 /var/lib/ghost-trials/artifacts /opt/robotics /opt/models /opt/ghost
  if ! command -v uv >/dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
    install -m 0755 /root/.local/bin/uv /usr/local/bin/uv
  fi
fi

echo "GPU host bootstrap complete for role: $ROLE"
