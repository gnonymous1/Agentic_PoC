#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if command -v python3.11 >/dev/null 2>&1; then
    PYTHON_BIN="python3.11"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  else
    PYTHON_BIN="python"
  fi
fi

if [[ ! -d "$VENV_DIR" ]]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

"$VENV_DIR/bin/python" -m ensurepip --upgrade >/dev/null 2>&1 || true
"$VENV_DIR/bin/python" -m pip install --upgrade pip setuptools "wheel<0.46"
"$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements.txt"

if [[ "${INSTALL_OPTIONAL:-0}" == "1" ]]; then
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-optional.txt"
fi

if [[ "${INSTALL_OPTIONAL_ML:-0}" == "1" ]]; then
  "$VENV_DIR/bin/python" -m pip install -r "$ROOT_DIR/requirements-optional-ml.txt"
fi

cd "$ROOT_DIR"
"$VENV_DIR/bin/python" -m pytest "$@"
