#!/usr/bin/env bash
# E2E smoke test — exercises the full Identyx stack through the gateway.
#
# Prerequisites: the stack is running (`docker compose -f infra/docker-compose.yml up -d --build`).
# Usage:            scripts/e2e_smoke_test.sh
# Override gateway: GATEWAY_URL=http://localhost:8100 scripts/e2e_smoke_test.sh
set -euo pipefail

BASE_URL="${GATEWAY_URL:-http://localhost:8100}"
TS="$(date +%s)"
EMAIL="e2e-${TS}@identyx.test"
USERNAME="e2e_user_${TS}"
PASSWORD="StrongPass!2026"

FAIL=0

fail() { echo "E2E FAIL: $1" >&2; exit 1; }
ok() { echo "  ok — $1"; }

wait_healthy() {
  echo "Waiting for gateway at $BASE_URL ..."
  for _ in $(seq 1 60); do
    if curl -fsS "$BASE_URL/health" >/dev/null 2>&1; then
      ok "gateway /health reachable"
      return 0
    fi
    sleep 2
  done
  fail "gateway did not become healthy within 120s"
}

register() {
  local body
  body=$(curl -sS -X POST "$BASE_URL/v1/auth/register" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"${EMAIL}\",\"username\":\"${USERNAME}\",\"password\":\"${PASSWORD}\"}")
  echo "$body"
}

echo "== Health =="
wait_healthy

echo "== Register =="
REGISTER_BODY="$(register)"
echo "$REGISTER_BODY" | python3 -c '
import json, sys
try:
    data = json.load(sys.stdin)
    assert "access_token" in data and "refresh_token" in data, "missing tokens"
    assert data.get("user", {}).get("email", "") != "", "missing user email"
except Exception as exc:
    raise SystemExit(f"register response invalid: {exc!r}")
' || fail "register returned an invalid payload"
ok "POST /v1/auth/register returned access/refresh tokens"

ACCESS_TOKEN="$(echo "$REGISTER_BODY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])')"
REFRESH_TOKEN="$(echo "$REGISTER_BODY" | python3 -c 'import json,sys; print(json.load(sys.stdin)["refresh_token"])')"

echo "== Authenticated user =="
ME_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/v1/users/me" -H "Authorization: Bearer ${ACCESS_TOKEN}")"
[ "$ME_STATUS" = "200" ] || fail "GET /v1/users/me expected 200, got ${ME_STATUS}"
ok "GET /v1/users/me returned 200 with a valid JWT"

echo "== Logout =="
LOGOUT_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE_URL/v1/auth/logout" \
  -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  -H 'Content-Type: application/json' \
  -d "{\"refresh_token\":\"${REFRESH_TOKEN}\"}")"
[ "$LOGOUT_STATUS" = "200" ] || fail "POST /v1/auth/logout expected 200, got ${LOGOUT_STATUS}"
ok "POST /v1/auth/logout revoked the session"

echo "== Observability =="
METRICS_BODY="$(curl -fsS "$BASE_URL/metrics")"
echo "$METRICS_BODY" | grep -q "http_requests_total" || fail "GET /metrics missing http_requests_total"
ok "GET /metrics exposed Prometheus metrics"

READY_STATUS="$(curl -sS -o /dev/null -w '%{http_code}' "$BASE_URL/ready")"
[ "$READY_STATUS" = "200" ] || fail "GET /ready expected 200, got ${READY_STATUS}"
ok "GET /ready reported the gateway as ready"

echo "E2E smoke test PASSED"
