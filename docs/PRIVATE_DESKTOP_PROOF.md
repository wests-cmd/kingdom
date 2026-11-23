# Private Desktop Proof — Offline Linux GUI Isolation

**Status: disposable engineering proof, not an installed Kingdom feature.**
Scope: one native Tk application under a dedicated in-container X11 display.
The AI/Kingdom runtime is **not yet wired to this worker**. No arbitrary app
execution, production credentials, browser networking, signed remote RPC,
user desktop observation, auto update or cross-OS control is claimed.

## Why this exists

Kingdom's existing Windows UI automation can affect the owner's foreground
application. This proof tests a separate Linux graphical desktop so that GUI
input can be performed **without attaching to the host's display**, using real
xdotool keyboard events rather than calling a GUI callback directly.

The CI proof starts Xvfb display :99 inside a disposable container, launches
a real Tk window, focuses it with X11, enters exact demo text using xdotool,
causes a real Return-key event, verifies the Tk app's persisted result, and
captures a PNG from the private Xvfb display.

## Isolation checks

The GitHub workflow uses a container with:
- No network connectivity (Docker network none).
- No host filesystem mounts, X11 sockets, display forwarding, device mounts or ports.
- Read-only root filesystem; private size-limited temporary filesystem.
- Unprivileged UID 10001, all Linux capabilities dropped, no new privileges.
- 64-PID, 512 MiB RAM and half-core CPU limits.
- No host process or IPC namespace sharing.

The independent Python evidence verifier reads the Docker HostConfig, worker
report and PNG screenshot. It rejects missing isolation flags, missing real
GUI test evidence and changed screenshot digests.

**A successfully restricted container is not a complete sandbox
certification.** Kernel vulnerabilities, Docker configuration, image supply
chain, input broker identity, runtime hardening, data retention and network
destination policy still require review. This test has *no* internet access,
so it cannot be used for production browsing or arbitrary autonomous work.

## Developer and CI execution

From the repository root, with Docker installed, use the exact commands in
.github/workflows/private-desktop-proof.yml. The commands deliberately run
only a fixture; never mount desktop X11 sockets, user home directories,
Docker socket, desktop database or production secrets into this worker.

The CI workflow retains private-desktop-offline-proof evidence for seven
days: the private-display PNG, worker report and sandbox HostConfig.

## Integration path — hard acceptance gates

1. **PASS — isolated offline GUI fixture:** exact-head CI must really build
   the image, run the X11 test and retain the screenshot. A unit mock is not
   sufficient.
2. **NEXT — signed Kingdom worker adapter:** add an authenticated broker
   bound to one existing task ID, capability set, approved executable,
   active lease, version and stop guard. Never accept raw host input commands.
3. **NEXT — per-task teardown and workload budget:** unique Xvfb/session,
   ephemeral home, resource caps, kill-on-stop and crash recovery, no blind
   replay of GUI clicks.
4. **NEXT — real applications:** permit a narrow reviewed binary allowlist
   only inside the isolated environment; adversarial clipboard/paste, focus,
   file and network tests on disposable devices.
5. **NEXT — native cross-platform production:** Windows must have a separate
   VM/session/dedicated worker (no foreground fallback); macOS requires a
   separately authorized platform-specific implementation; pass installed
   real-machine security commissioning #172, noninterference and updates.

Track the full product definition under
[private desktop issue #186](https://github.com/wests-cmd/kingdom/issues/186)
and [daily-driver release issue #188](https://github.com/wests-cmd/kingdom/issues/188).
Do not call the offline fixture a complete AI computer-control harness.
