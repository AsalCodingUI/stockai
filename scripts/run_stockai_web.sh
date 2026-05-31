#!/bin/zsh
set -euo pipefail

cd /Users/mac/Downloads/stockai-main
exec /opt/homebrew/bin/uv run uvicorn stockai.web.app:app --host 0.0.0.0 --port 8000
