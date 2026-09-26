#!/usr/bin/env bash
# CoCo CLI PreToolUse hook — blocks destructive or privacy-unsafe operations.
# Reads the tool invocation payload on stdin. Non-zero exit blocks the call.
set -euo pipefail
payload="$(cat)"
lower="$(printf '%s' "$payload" | tr '[:upper:]' '[:lower:]')"

block() { echo "BLOCKED by carelens pretooluse hook: $1" >&2; exit 2; }

# 1. never drop or truncate the governed layers
case "$lower" in
  *"drop database carelens"*|*"drop schema carelens"*) block "dropping CareLens schemas needs a human" ;;
  *"truncate table carelens.gold"*|*"truncate table carelens.curated"*) block "truncating curated/gold layers" ;;
esac

# 2. governance must not be silently unset
case "$lower" in
  *"unset masking policy"*|*"drop masking policy"*|*"drop row access policy"*|*"unset tag synthetic_data_flag"*)
    block "removing a masking/row-access policy or the synthetic-data flag" ;;
esac

# 3. no external data pulls into the patient layers without review
case "$lower" in
  *"copy into carelens"*"s3://"*|*"copy into carelens"*"azure://"*|*"copy into carelens"*"gcs://"*)
    block "external-stage load into CareLens; confirm the source is fully synthetic first" ;;
esac

# 4. refuse anything that looks like real PHI being written inline
if printf '%s' "$payload" | grep -Eqi '\b[0-9]{3}-[0-9]{2}-[0-9]{4}\b'; then
  block "payload contains an SSN-shaped value"
fi

exit 0
