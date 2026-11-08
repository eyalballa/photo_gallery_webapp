#!/usr/bin/env bash
# End-to-end tests: start the app image with the golden photos as its album, then run e2e/ against it over HTTP
# from the test image, both on a private Docker network (nothing is published on the host).
#
#   docker build -t photo-wall . && docker build --target test -t photo-wall-test .
#   e2e/run.sh [app image] [test image]
set -euo pipefail

APP=${1:-photo-wall:latest}
TESTER=${2:-photo-wall-test:latest}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
NAME=wall-e2e-$$
PASSCODE=e2e-passcode

cleanup() {
  status=$?
  if [ $status -ne 0 ]; then
    echo "--- app logs"
    docker logs "$NAME" 2>&1 | tail -50 || true
  fi
  docker rm -f "$NAME" >/dev/null 2>&1 || true
  docker network rm "$NAME" >/dev/null 2>&1 || true
  exit $status
}
trap cleanup EXIT

# a missing bind-mount source becomes an empty directory, and the app dies on it
[ -f "$ROOT/e2e/wall.yaml" ] || { echo "missing $ROOT/e2e/wall.yaml" >&2; exit 1; }
docker network create "$NAME" >/dev/null
docker run -d --name "$NAME" --network "$NAME" --network-alias wall \
  -e PASSCODE="$PASSCODE" -e SESSION_SECRET="$(printf 'e2e%.0s' {1..16})" -e COOKIE_SECURE=false \
  -v "$ROOT/e2e/wall.yaml:/app/backend/config.yaml:ro" \
  -v "$ROOT/backend/golden/input:/photos:ro" \
  "$APP" python -m wall --source fake:/photos serve --host 0.0.0.0 >/dev/null

docker run --rm --network "$NAME" \
  -e WALL_URL=http://wall:8000 -e WALL_PASSCODE="$PASSCODE" -e PYTHONPATH=/app/backend \
  -v "$ROOT/e2e:/e2e:ro" -v "$ROOT/backend/golden/input:/photos:ro" \
  "$TESTER" pytest -q -p no:cacheprovider /e2e
