#!/bin/sh
# Dedicated graphical session inside an offline disposable Linux container.
set -eu
umask 077
if [ "$DISPLAY" != ":99" ]; then
  echo "Refusing to attach to any display other than the private :99 session" >&2
  exit 40
fi

# Xvfb cannot create the X11 socket parent as a non-root UID; make it
# inside the private tmpfs (never use the host's X11 socket directory).
mkdir -p /tmp/.X11-unix
chmod 1777 /tmp/.X11-unix
Xvfb :99 -screen 0 800x600x24 -nolisten tcp -noreset -ac &
server_pid=$!
app_pid=""
cleanup() {
  if [ -n "$app_pid" ]; then kill "$app_pid" 2>/dev/null || true; fi
  kill "$server_pid" 2>/dev/null || true
  wait "$server_pid" 2>/dev/null || true
}
trap cleanup EXIT HUP INT TERM

ready=0
i=0
while [ "$i" -lt 50 ]; do
  if xdpyinfo -display :99 >/dev/null 2>&1; then ready=1; break; fi
  i=$((i + 1))
  sleep 0.1
done
if [ "$ready" -ne 1 ]; then
  echo "Isolated Xvfb display never became ready" >&2
  exit 41
fi

python3 -B /opt/kingdom/demo.py &
app_pid=$!
python3 -B /opt/kingdom/probe.py
