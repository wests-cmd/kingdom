"""Offline, disposable native GUI fixture for the private-desktop containment proof.

This deliberately contains no network code, file browser or command launcher.
"""
from pathlib import Path
import json
import tkinter as tk

EXPECTED = "kingdom-private-control-ok"
PROOF = Path("/tmp/private-desktop-confirmation.txt")
TARGET = Path("/tmp/private-desktop-target.json")

root = tk.Tk()
root.title("Kingdom Private Desktop Proof")
root.geometry("550x260+45+45")
root.configure(bg="#16181d")

heading = tk.Label(
    root, text="Private Kingdom worker — disposable GUI fixture",
    font=("DejaVu Sans", 13), fg="#e5e7eb", bg="#16181d"
)
heading.pack(pady=(22, 18))
entry = tk.Entry(root, width=44, font=("DejaVu Sans", 12))
entry.pack(pady=(5, 12))
status = tk.Label(root, text="Waiting for private X11 keyboard input",
                  fg="#9ca3af", bg="#16181d")
status.pack(pady=8)


def confirm(_event=None):
    # Input is delivered through the container's Xvfb display, not the host
    # desktop and not a direct invocation of this callback.
    value = entry.get()
    if value == EXPECTED:
        PROOF.write_text(value, encoding="utf-8")
        status.configure(text="Verified private UI input", fg="#93c5fd")
    else:
        status.configure(text="Unexpected input; proof refused", fg="#ef4444")


entry.bind("<Return>", confirm)
tk.Button(root, text="Confirm private input", command=confirm).pack(pady=8)


def publish_target():
    # This disposable fixture provides the entry field's geometry to the
    # test driver. The driver must STILL perform actual X11 pointer/keyboard
    # events; this does not claim screenshot-based generic UI perception.
    root.update_idletasks()
    if not entry.winfo_ismapped():
        root.after(75, publish_target)
        return
    target = {
        "x": entry.winfo_rootx() + entry.winfo_width() // 2,
        "y": entry.winfo_rooty() + entry.winfo_height() // 2,
    }
    TARGET.write_text(json.dumps(target), encoding="utf-8")


root.after(100, publish_target)
root.mainloop()
