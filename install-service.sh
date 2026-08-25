#!/usr/bin/env bash
#
# Install Shrimp Cam as a systemd service, using the *current* user and the
# repo's actual location. This avoids the common "status=217/USER" failure that
# happens when the unit file hardcodes a username (e.g. "pi") that doesn't exist
# on your Pi.
#
# Usage:
#   ./install-service.sh                 # no auth (trusted LAN only)
#   SHRIMPCAM_USER=me SHRIMPCAM_PASS=s3cret ./install-service.sh
#
set -euo pipefail

UNIT_NAME="shrimpcam.service"
DEST="/etc/systemd/system/${UNIT_NAME}"

# Resolve the repo directory (where this script lives), regardless of cwd.
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE="${DIR}/${UNIT_NAME}"

# Run as the invoking user, not root, even when called via sudo.
RUN_USER="${SUDO_USER:-$(id -un)}"

if [[ "${RUN_USER}" == "root" ]]; then
  echo "Refusing to install a service that runs as root." >&2
  echo "Run this script as your normal user (it will call sudo itself)." >&2
  exit 1
fi

if [[ ! -f "${TEMPLATE}" ]]; then
  echo "Cannot find ${TEMPLATE}" >&2
  exit 1
fi

if [[ ! -f "${DIR}/app.py" ]]; then
  echo "Cannot find app.py in ${DIR} — run this from the repo checkout." >&2
  exit 1
fi

echo "Installing ${UNIT_NAME}"
echo "  user:      ${RUN_USER}"
echo "  directory: ${DIR}"

# Build the unit from the template, substituting the placeholders.
tmp="$(mktemp)"
trap 'rm -f "${tmp}"' EXIT
sed -e "s|__USER__|${RUN_USER}|g" -e "s|__DIR__|${DIR}|g" "${TEMPLATE}" > "${tmp}"

# Optionally bake in Basic Auth credentials if they're set in the environment.
if [[ -n "${SHRIMPCAM_USER:-}" ]]; then
  if [[ -z "${SHRIMPCAM_PASS:-}" ]]; then
    echo "SHRIMPCAM_USER is set but SHRIMPCAM_PASS is empty — refusing." >&2
    exit 1
  fi
  # Replace the commented placeholders with the real values.
  sed -i \
    -e "s|^# Environment=SHRIMPCAM_USER=.*|Environment=SHRIMPCAM_USER=${SHRIMPCAM_USER}|" \
    -e "s|^# Environment=SHRIMPCAM_PASS=.*|Environment=SHRIMPCAM_PASS=${SHRIMPCAM_PASS}|" \
    "${tmp}"
  echo "  auth:      enabled for user '${SHRIMPCAM_USER}'"
else
  echo "  auth:      disabled (LAN only) — set SHRIMPCAM_USER/SHRIMPCAM_PASS to enable"
fi

sudo install -m 644 "${tmp}" "${DEST}"
# The unit may contain a password, so keep it readable by root only.
if [[ -n "${SHRIMPCAM_USER:-}" ]]; then
  sudo chmod 600 "${DEST}"
fi

sudo systemctl daemon-reload
sudo systemctl enable --now "${UNIT_NAME}"

echo
sudo systemctl status "${UNIT_NAME}" --no-pager || true
echo
echo "Logs:  journalctl -u ${UNIT_NAME} -f"
echo "Open:  http://$(hostname -I | awk '{print $1}'):${PORT:-8080}/"
