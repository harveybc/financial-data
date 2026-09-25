#!/bin/sh
# Install and start the point-in-time capture as a systemd --user timer.
#
# Everything machine-specific is written to ~/.config/financial-data/point-in-time-capture.env,
# which is OUTSIDE the repository: the unit files carry no path of this machine.
#
# Usage:  sh _scripts/systemd/install_point_in_time_capture.sh [PYTHON] [STORE_ROOT]
#
# Defaults: the python on PATH, and $XDG_STATE_HOME/financial-data/point_in_time.
# Verify afterwards with:
#   systemctl --user list-timers financial-data-point-in-time-capture.timer
#   systemctl --user start financial-data-point-in-time-capture.service
#   tail -1 "$FD_PIT_LOG"
set -eu

REPO=$(cd "$(dirname "$0")/../.." && pwd)
PYTHON=${1:-$(command -v python3)}
STATE=${XDG_STATE_HOME:-$HOME/.local/state}/financial-data
STORE=${2:-$STATE/point_in_time}
CONF=$HOME/.config/financial-data
UNITS=${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user

mkdir -p "$CONF" "$UNITS" "$STATE/logs" "$STORE"
umask 077
cat > "$CONF/point-in-time-capture.env" <<ENV
# written by install_point_in_time_capture.sh; not tracked by git
FD_PYTHON=$PYTHON
FD_REPO=$REPO
FD_PIT_STORE=$STORE
FD_PIT_LOG=$STATE/logs/point_in_time_capture.log
FD_PIT_LAST_RUN=$STATE/logs/point_in_time_capture_last_run.json
ENV

cp "$REPO/_scripts/systemd/financial-data-point-in-time-capture.service" "$UNITS/"
cp "$REPO/_scripts/systemd/financial-data-point-in-time-capture.timer" "$UNITS/"
systemctl --user daemon-reload
systemctl --user enable --now financial-data-point-in-time-capture.timer
systemctl --user list-timers --all financial-data-point-in-time-capture.timer
