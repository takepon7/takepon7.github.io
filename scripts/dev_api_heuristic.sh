#!/usr/bin/env bash
set -euo pipefail

GITAI_DATA_DIR="${GITAI_DATA_DIR:-data/scoring}" \
GITAI_PUZZLE_DIR="${GITAI_PUZZLE_DIR:-data/puzzle}" \
GITAI_MODEL="${GITAI_MODEL:-heuristic}" \
GITAI_OCR="${GITAI_OCR:-fingerprint}" \
HF_HOME="${HF_HOME:-.cache/huggingface}" \
TORCH_HOME="${TORCH_HOME:-.cache/torch}" \
XDG_CACHE_HOME="${XDG_CACHE_HOME:-.cache/xdg}" \
.venv310/bin/python -m uvicorn gitai_phase0.server:app --host 127.0.0.1 --port 8000
