#!/usr/bin/env bash
# Release helper. Usage:
#   scripts/release.sh version             print the version in index.html
#   scripts/release.sh check               the version in index.html, the UI label and the top CHANGELOG entry agree
#   scripts/release.sh notes X.Y.Z         print the CHANGELOG notes for X.Y.Z
#   scripts/release.sh verify-live X.Y.Z   wait (up to 10 min) until the live site serves X.Y.Z
set -euo pipefail
cd "$(dirname "$0")/.."
LIVE_URL="${LIVE_URL:-https://jonahthecodah.github.io/battleship-game/}"

version() { sed -n 's/.*<meta name="app-version" content="\([^"]*\)".*/\1/p' "${1:-index.html}" | head -1; }

case "${1:-}" in
  version) version ;;
  check)
    v=$(version)
    [[ "$v" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || { echo "index.html version '$v' is not MAJOR.MINOR.PATCH"; exit 1; }
    grep -q "id=\"app-version\"[^>]*>v$v<" index.html || { echo "UI label does not show v$v"; exit 1; }
    top=$(sed -n 's/^## \[\([0-9][^]]*\)\].*/\1/p' CHANGELOG.md | head -1)
    [ "$top" = "$v" ] || { echo "Top CHANGELOG entry is $top, index.html says $v"; exit 1; }
    echo "Version $v is consistent" ;;
  notes)
    awk -v v="${2:?version}" '$0 ~ "^## \\[" v "\\]" {on=1; next} /^## \[/ {on=0} on' CHANGELOG.md | sed '/./,$!d' ;;
  verify-live)
    want="${2:?version}"
    for i in $(seq 1 60); do
      got=$(curl -fsSL -H 'Cache-Control: no-cache' "$LIVE_URL?v=$want-$i" -o /tmp/live.html && version /tmp/live.html || true)
      [ "$got" = "$want" ] && { echo "Live site $LIVE_URL serves v$got"; exit 0; }
      echo "Live site serves '${got:-unknown}', waiting for $want..."; sleep 10
    done
    echo "Live site did not show $want within 10 minutes"; exit 1 ;;
  *) sed -n '2,6p' "$0"; exit 1 ;;
esac
