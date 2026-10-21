#!/bin/bash
# The old name for a wait that ends on the grab: noga_wait.sh <args> = noga_watchdog.sh --until-locked <args>.
exec "$(dirname "$0")/noga_watchdog.sh" --until-locked "$@"
