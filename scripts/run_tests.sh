#!/usr/bin/env bash
# Serves the game on port 8080 and runs every browser test suite, even if an earlier one fails.
# Exits non-zero if any suite failed.
set -uo pipefail
cd "$(dirname "$0")/.."
PORT=8080
if ! curl -fs -o /dev/null "http://localhost:$PORT/"; then
  python3 -m http.server "$PORT" > /dev/null 2>&1 &
  SERVER=$!
  trap 'kill $SERVER 2>/dev/null' EXIT
  for _ in $(seq 1 50); do curl -fs -o /dev/null "http://localhost:$PORT/" && break; sleep 0.2; done
fi
failed=()
for suite in tests/test_game.py tests/test_qa_extra.py; do
  echo "::group::$suite"
  python3 "$suite" || failed+=("$suite")
  echo "::endgroup::"
done
if [ ${#failed[@]} -gt 0 ]; then echo "Failed suites: ${failed[*]}"; exit 1; fi
echo "All test suites passed"
