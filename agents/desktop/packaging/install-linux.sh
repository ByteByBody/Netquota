#!/bin/sh
# NetQuota desktop agent installer for Linux (systemd).
#
# Usage:
#   sudo ./install-linux.sh
#
# Enroll the device as the target user after installation:
#   sudo -u netquota NETQUOTA_AGENT_CONFIG_DIR=/var/lib/netquota \
#       netquota-agent enroll --server https://netquota.local --code <CODE> --name "PC"
set -eu

SERVICE_USER="${NETQUOTA_SERVICE_USER:-netquota}"
INSTALL_DIR="${NETQUOTA_INSTALL_DIR:-/opt/netquota}"
CONFIG_DIR="${NETQUOTA_AGENT_CONFIG_DIR:-/var/lib/netquota}"
VENV="${INSTALL_DIR}/venv"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root (sudo)." >&2
    exit 1
fi

echo "Creating service user ${SERVICE_USER}..."
id -u "${SERVICE_USER}" >/dev/null 2>&1 || useradd --system --create-home --home-dir "${CONFIG_DIR}" "${SERVICE_USER}"

echo "Installing files into ${INSTALL_DIR}..."
mkdir -p "${INSTALL_DIR}"
cp -r "$(dirname "$0")/.." "${INSTALL_DIR}/agent"

echo "Creating virtual environment..."
python3 -m venv "${VENV}"
"${VENV}/bin/pip" install --upgrade pip >/dev/null
"${VENV}/bin/pip" install "${INSTALL_DIR}/agent[secure]"

ln -sf "${VENV}/bin/netquota-agent" /usr/local/bin/netquota-agent

mkdir -p "${CONFIG_DIR}"
chown -R "${SERVICE_USER}:${SERVICE_USER}" "${CONFIG_DIR}"

echo "Installing systemd unit..."
sed "s#/var/lib/netquota#${CONFIG_DIR}#g; s#User=netquota#User=${SERVICE_USER}#; s#Group=netquota#Group=${SERVICE_USER}#" \
    "${INSTALL_DIR}/agent/packaging/netquota-agent.service" \
    > /etc/systemd/system/netquota-agent.service

systemctl daemon-reload
systemctl enable --now netquota-agent.service || echo "Enable after enrollment."

echo "Done. Enroll with:"
echo "  sudo -u ${SERVICE_USER} NETQUOTA_AGENT_CONFIG_DIR=${CONFIG_DIR} netquota-agent enroll --server <URL> --code <CODE> --name \"<NAME>\""