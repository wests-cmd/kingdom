"""Bounded, read-only Windows foreground observation; no permission changes."""

import json
import subprocess
import sys

_TIMEOUT_SECONDS = 12
_MAX_OUTPUT_BYTES = 200000
_MAX_INPUT_BYTES = 4096
_MAX_CONTROLS = 100
_MAX_DEPTH = 8
_MAX_TEXT_CHARS = 15000


def _failure(code):
    return {"ok": False, "error": code}


def _foreground_window():
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL("user32", use_last_error=True)

    user32.GetForegroundWindow.argtypes = []
    user32.GetForegroundWindow.restype = wintypes.HWND

    user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    user32.GetWindowTextLengthW.restype = ctypes.c_int

    user32.GetWindowTextW.argtypes = [
        wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
    ]
    user32.GetWindowTextW.restype = ctypes.c_int

    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        raise RuntimeError("foreground_unavailable")

    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        raise RuntimeError("title_unavailable")

    buffer = ctypes.create_unicode_buffer(length + 1)
    copied = user32.GetWindowTextW(hwnd, buffer, length + 1)

    if copied <= 0 or copied != length:
        raise RuntimeError("title_unavailable")

    return int(hwnd), buffer.value


def _password_state(wrapper):
    try:
        value = wrapper.element_info.element.CurrentIsPassword
        if type(value) is bool:
            return value
        if type(value) is int and value in (0, 1):
            return bool(value)
    except Exception:
        pass
    return None


def _visible(wrapper):
    try:
        element = wrapper.element_info.element
        offscreen = element.CurrentIsOffscreen

        if type(offscreen) not in (bool, int):
            return False
        if offscreen not in (False, 0):
            return False

        rect = wrapper.rectangle()
        return (
            int(rect.right) > int(rect.left)
            and int(rect.bottom) > int(rect.top)
        )
    except Exception:
        return False


def _rectangle(wrapper):
    try:
        rect = wrapper.rectangle()
        return {
            "left": int(rect.left),
            "top": int(rect.top),
            "right": int(rect.right),
            "bottom": int(rect.bottom),
        }
    except Exception:
        return {
            "left": 0,
            "top": 0,
            "right": 0,
            "bottom": 0,
        }


def _safe_property(element, attribute):
    try:
        value = getattr(element, attribute)
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _edit_value(wrapper):
    """Read only an individually verified non-password Edit control."""
    try:
        value = wrapper.iface_value.CurrentValue
        return value if isinstance(value, str) else ""
    except Exception:
        return ""


def _observe_worker(params):
    import platform
    import time
    from collections import deque

    if platform.system() != "Windows":
        return _failure("windows_required")

    try:
        from pywinauto import Desktop
    except ImportError:
        return _failure("pywinauto_unavailable")

    expected_title = params.get("window_title")
    if not isinstance(expected_title, str) or not expected_title:
        return _failure("invalid_window_title")

    try:
        hwnd, title = _foreground_window()

        if title != expected_title:
            return _failure("foreground_window_mismatch")

        root = (
            Desktop(backend="uia")
            .window(handle=hwnd)
            .wrapper_object()
        )

        queue = deque([(root, 0)])
        visited = set()
        controls = []
        text_used = 0
        examined = 0

        while queue and examined < _MAX_CONTROLS:
            wrapper, depth = queue.popleft()
            examined += 1

            try:
                element = wrapper.element_info
                runtime_id = tuple(element.element.GetRuntimeId())
            except Exception:
                continue

            if runtime_id in visited:
                continue
            visited.add(runtime_id)

            # Never inspect text or names of offscreen elements.
            if not _visible(wrapper):
                continue

            password = _password_state(wrapper)

            # Unknown password state is treated as sensitive.
            if password is None:
                continue

            if password:
                control_type = "Password"
                name = "[REDACTED]"
                automation_id = ""
            else:
                control_type = _safe_property(
                    element, "control_type"
                )
                name = _safe_property(element, "name")
                automation_id = _safe_property(
                    element, "automation_id"
                )

            remaining = max(0, _MAX_TEXT_CHARS - text_used)
            name = name[:remaining]
            text_used += len(name)

            remaining = max(0, _MAX_TEXT_CHARS - text_used)
            automation_id = automation_id[:remaining]
            text_used += len(automation_id)

            record = {
                "name": name,
                "control_type": control_type,
                "automation_id": automation_id,
                "rectangle": _rectangle(wrapper),
            }

            # DocumentRange is intentionally never read.
            # Parent Document text may contain password descendants.
            if not password and control_type == "Edit":
                remaining = max(
                    0, _MAX_TEXT_CHARS - text_used
                )
                if remaining:
                    value = _edit_value(wrapper)[:remaining]
                    if value:
                        record["text"] = value
                        text_used += len(value)

            controls.append(record)

            if depth >= _MAX_DEPTH:
                continue

            try:
                children = wrapper.children()
            except Exception:
                continue

            # Bound traversal memory as well as examined controls.
            remaining_slots = max(
                0, _MAX_CONTROLS - examined - len(queue)
            )
            for child in children[:remaining_slots]:
                queue.append((child, depth + 1))

        # A foreground change invalidates the entire observation.
        final_hwnd, final_title = _foreground_window()

        if final_hwnd != hwnd or final_title != expected_title:
            return _failure("foreground_changed")

        return {
            "ok": True,
            "window_handle": hwnd,
            "window_title": title,
            "observed_at": time.time(),
            "controls": controls,
        }

    except Exception:
        return _failure("observation_failed")


def desktop_observe(params):
    """Run one bounded foreground observation in a child Python process.

    The caller must authenticate the owner and authorize the exact title.
    This function grants no capabilities or permissions.
    """
    import platform

    if platform.system() != "Windows":
        return _failure("windows_required")

    if not isinstance(params, dict):
        return _failure("invalid_parameters")

    title = params.get("window_title")
    if not isinstance(title, str) or not title:
        return _failure("invalid_window_title")

    try:
        payload = json.dumps(
            {"window_title": title},
            ensure_ascii=False,
        ).encode("utf-8")

        if len(payload) > _MAX_INPUT_BYTES:
            return _failure("input_too_large")

        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "backend.runtime.desktop_observation",
                "--worker",
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
            creationflags=getattr(
                subprocess, "CREATE_NO_WINDOW", 0
            ),
        )

        try:
            output, _ = process.communicate(
                input=payload,
                timeout=_TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            return _failure("observation_timeout")

        if process.returncode != 0:
            return _failure("worker_failed")

        if len(output) > _MAX_OUTPUT_BYTES:
            return _failure("output_too_large")

        result = json.loads(output.decode("utf-8"))

        if not isinstance(result, dict):
            return _failure("invalid_worker_response")

        if result.get("ok") is not True:
            allowed = {
                "windows_required",
                "pywinauto_unavailable",
                "invalid_window_title",
                "foreground_window_mismatch",
                "foreground_changed",
                "observation_failed",
            }
            code = result.get("error")
            return _failure(
                code if code in allowed else "observation_failed"
            )

        if (
            type(result.get("window_handle")) is not int
            or result.get("window_handle") <= 0
            or result.get("window_title") != title
            or type(result.get("observed_at")) not in (int, float)
            or not isinstance(result.get("controls"), list)
            or len(result["controls"]) > _MAX_CONTROLS
        ):
            return _failure("invalid_worker_response")

        return result

    except Exception:
        return _failure("observation_failed")


def _worker_main():
    """Emit exactly one JSON object on stdout."""
    import contextlib
    import os

    result = _failure("worker_failed")

    try:
        raw = sys.stdin.buffer.read(_MAX_INPUT_BYTES + 1)

        if len(raw) > _MAX_INPUT_BYTES:
            result = _failure("input_too_large")
        else:
            params = json.loads(raw.decode("utf-8"))

            if not isinstance(params, dict):
                result = _failure("invalid_parameters")
            else:
                # Redirect native and Python library stdout away
                # from the JSON protocol channel.
                original_fd = os.dup(1)

                try:
                    sys.stdout.flush()
                    os.dup2(2, 1)

                    with contextlib.redirect_stdout(sys.stderr):
                        result = _observe_worker(params)

                finally:
                    sys.stdout.flush()
                    os.dup2(original_fd, 1)
                    os.close(original_fd)

    except Exception:
        result = _failure("worker_failed")

    try:
        output = json.dumps(
            result,
            ensure_ascii=False,
            separators=(",", ":"),
        ).encode("utf-8")

        if len(output) > _MAX_OUTPUT_BYTES:
            output = json.dumps(
                _failure("output_too_large")
            ).encode("utf-8")

        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()

    except Exception:
        sys.stdout.write(
            '{"ok":false,"error":"worker_failed"}'
        )
        sys.stdout.flush()


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "--worker":
        _worker_main()
    else:
        sys.stdout.write(
            '{"ok":false,"error":"worker_mode_required"}'
        )