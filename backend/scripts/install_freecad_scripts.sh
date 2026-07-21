#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_SCRIPT="${BACKEND_DIR}/freecad_scripts/parse_step.py"
TARGET_DIR="${CAD_SCRIPT_DIR:?CAD_SCRIPT_DIR is required}"
TARGET_SCRIPT="${TARGET_DIR}/parse_step.py"

mkdir -p "${TARGET_DIR}"
cp "${SOURCE_SCRIPT}" "${TARGET_SCRIPT}"
chmod 644 "${TARGET_SCRIPT}"
echo "${TARGET_SCRIPT}"
