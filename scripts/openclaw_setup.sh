#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${1:-$(pwd)}"
AUTH_CHOICE="skip"
AUTH_ARGS=()

if [[ -n "${OPENAI_API_KEY:-}" ]]; then
  AUTH_CHOICE="openai-api-key"
  AUTH_ARGS+=(--openai-api-key "$OPENAI_API_KEY")
fi

if ! command -v openclaw >/dev/null 2>&1; then
  echo "Installing openclaw..."
  npm install -g openclaw@latest
fi

echo "Bootstrapping OpenClaw workspace: $WORKSPACE"
openclaw onboard \
  --non-interactive \
  --accept-risk \
  --auth-choice "$AUTH_CHOICE" \
  --skip-channels \
  --skip-ui \
  --skip-skills \
  --skip-daemon \
  --skip-health \
  --workspace "$WORKSPACE" \
  "${AUTH_ARGS[@]}"

openclaw config set agents.defaults.workspace "\"$WORKSPACE\"" --json
openclaw config set browser.enabled true --json
openclaw config set browser.defaultProfile '"openclaw"' --json
openclaw config set browser.headless false --json
openclaw config set agents.defaults.sandbox.mode '"off"' --json
openclaw config set agents.defaults.heartbeat.every '"0m"' --json
openclaw models set openai/gpt-5.1-codex

openclaw gateway install || true
openclaw gateway start

echo
echo "OpenClaw setup complete."
echo "Next steps:"
echo "  1) If auth is missing: run openclaw onboard --auth-choice openai-api-key --openai-api-key \"\$OPENAI_API_KEY\""
echo "  2) openclaw browser start --browser-profile openclaw"
echo "  3) openclaw skills list --eligible"
