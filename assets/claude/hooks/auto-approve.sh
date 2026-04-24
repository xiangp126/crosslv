#!/bin/bash
# PreToolUse hook: auto-approve ALL tool calls (Bash, Read, Write, Edit, MCP, etc.)
cat > /dev/null
printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"auto-approved"}}\n'
