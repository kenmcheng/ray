#!/usr/bin/env bash
set -x
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE:-$0}")"; pwd)
cd "$ROOT_DIR"

clean_up() {
  ray stop --force
}
trap clean_up EXIT

CYPRESS_VERSION=14.2.1

echo "Installing cypress"
if [[ -n "$BUILDKITE" ]]; then
  apt-get update -qq
  apt install -y libgtk2.0-0 libgtk-3-0 libgbm-dev libnotify-dev libgconf-2-4 libnss3 libxss1 libasound2 libxtst6 xauth xvfb
  sudo npm install "cypress@$CYPRESS_VERSION"
else
  which cypress || npm install "cypress@$CYPRESS_VERSION" -g
fi

ray stop --force
ray start --head --dashboard-port=8653 --dashboard-host=0.0.0.0

sleep 5 # Wait for Ray dashboard to become ready
curl localhost:8653 || cat /tmp/ray/session_latest/logs/dashboard.log

node_modules/.bin/cypress run --project . --headless

# Run frontend UI tests
(
  cd ../client
  CI=true npm test
)
