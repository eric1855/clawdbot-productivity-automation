#!/usr/bin/env bash
set -euo pipefail

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[dev]"
python -m playwright install chromium

if [[ ! -f config/application.yaml ]]; then
  cp config/application.example.yaml config/application.yaml
fi

if [[ ! -f config/qa_defaults.yaml ]]; then
  cp config/qa_defaults.example.yaml config/qa_defaults.yaml
fi

if [[ ! -f config/resume_template.md ]]; then
  cp config/resume_template.example.md config/resume_template.md
fi

./scripts/openclaw_setup.sh "$(pwd)"

echo "Bootstrap complete."
echo "Next:"
echo "  1) edit config/application.yaml + config/qa_defaults.yaml"
echo "  2) export OPENAI_API_KEY=... (optional)"
echo "  3) run ./scripts/openclaw_apply_handshake.sh 25 dry-run"
