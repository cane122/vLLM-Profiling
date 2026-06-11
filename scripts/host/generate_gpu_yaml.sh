#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
OUT_FILE="${ROOT_DIR}/.config/gpus.yaml"

mkdir -p "${ROOT_DIR}/.config"

mapfile -t render_devices < <(ls /dev/dri/renderD* 2>/dev/null | sort || true)

if [[ ${#render_devices[@]} -eq 0 ]]; then
  echo "No /dev/dri/renderD* devices found; cannot generate ${OUT_FILE}" >&2
  exit 1
fi

echo "gpus:" > "${OUT_FILE}"

for dev in "${render_devices[@]}"; do
  name=$(udevadm info --query=property --name="$dev" 2>/dev/null \
    | awk -F= '/^ID_MODEL_FROM_DATABASE=/{print $2; found=1; exit} /^ID_MODEL=/{if (!found) print $2}' \
    | sed 's/_/ /g' \
    || true)

  if [[ -z "${name}" ]]; then
    name="${dev##*/}"
  fi

  cat >> "${OUT_FILE}" <<EOF
  - name: "${name}"
    device: "${dev}"
    disabled: false
EOF
done

echo "Generated ${OUT_FILE} with ${#render_devices[@]} GPU device(s)."
