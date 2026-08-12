#!/usr/bin/env bash
set -euo pipefail

host="${1:-bezrabotnyi.com}"
domain="${2:-all.bezrabotnyi.com}"
expected_ipv4="${3:-95.165.165.65}"

if ! dig +short A "$domain" | grep -Fxq "$expected_ipv4"; then
  echo "DNS for $domain is not yet $expected_ipv4; TLS was not changed." >&2
  exit 2
fi

ssh "$host" "sudo certbot --nginx --non-interactive --agree-tos --redirect -d '$domain'"
ssh "$host" "curl -fsSI --resolve '$domain:443:$expected_ipv4' 'https://$domain/walk.html' | head -1"
