#!/usr/bin/env bash
# Quick API connectivity test. Run with backend at http://localhost:8000
set -e
BASE="${1:-http://localhost:8000}"
echo "Testing API at $BASE"
echo ""

# Django admin (302 redirect is ok)
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/admin/" || true)
if [ "$CODE" = "302" ] || [ "$CODE" = "200" ] || [ "$CODE" = "301" ]; then
  echo "  GET /admin/        -> $CODE OK"
else
  echo "  GET /admin/        -> $CODE (expected 302/200)"
fi

# API auth login (400 without body is ok)
CODE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE/api/auth/login/" -H "Content-Type: application/json" -d '{}' || true)
if [ "$CODE" = "400" ] || [ "$CODE" = "401" ]; then
  echo "  POST /api/auth/login/ -> $CODE (auth endpoint reachable)"
else
  echo "  POST /api/auth/login/ -> $CODE"
fi

echo ""
echo "Done. See TESTING_CHECKLIST.md for full flow tests."
