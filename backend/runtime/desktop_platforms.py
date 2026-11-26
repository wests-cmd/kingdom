"""Bounded foreground identity probes, not accessibility or input certification.

Optional host-native adapters. No shell, package installation or permission grant.
Do not treat an identity-only observation as proof of application content.
"""
import os
import platform
import shutil
import subprocess
import time


def _command(argv):
    output=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
                          timeout=3,check=True,shell=False)
    if len(output.stdout)>4096:
        raise ValueError("Foreground identity too large")
    return output.stdout.decode("utf-8",errors="strict").rstrip("\r\n")


def _linux_identity():
    # X11 only. Never fall back to XWayland on a Wayland session.
    if not os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY") or os.environ.get("XDG_SESSION_TYPE")=="wayland":
        raise RuntimeError("X11 desktop required")
    exe=shutil.which("xdotool")
    if not exe:
        raise RuntimeError("xdotool is not installed")
    handle=int(_command([exe,"getactivewindow"]))
    title=_command([exe,"getwindowname",str(handle)])
    if int(_command([exe,"getactivewindow"]))!=handle:
        raise ValueError("Foreground changed")
    return handle,title


def _mac_identity():
    exe=shutil.which("osascript")
    if not exe:
        raise RuntimeError("osascript unavailable")
    # Constant script: no model or user-supplied code is interpolated.
    script="""tell application "System Events"
    set p to first application process whose frontmost is true
    if (count of windows of p) is 0 then error "No window"
    return ((unix id of p) as text) & linefeed & (name of front window of p)
end tell"""
    pid,sep,title=_command([exe,"-e",script]).partition("\n")
    if not sep:
        raise ValueError("No window identity")
    return int(pid),title


def observe_identity(params, system=None):
    system=system or platform.system()
    probe={"Linux":_linux_identity,"Darwin":_mac_identity}.get(system)
    if not probe:
        return {"ok":False,"error":"unsupported_platform"}
    title=params.get("window_title") if isinstance(params,dict) else None
    if not isinstance(title,str) or not title.strip() or len(title)>500:
        return {"ok":False,"error":"invalid_window_title"}
    try:
        handle,actual=probe()
        if handle<=0 or actual!=title or probe()!=(handle,actual):
            return {"ok":False,"error":"foreground_changed"}
        return {"ok":True,"window_title":actual,"window_handle":handle,"observed_at":time.time(),
                "controls":[],"observation_scope":"foreground_identity_only","input_supported":False,
                "platform":system}
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError):
        return {"ok":False,"error":"foreground_probe_unavailable"}
