"""Offline, disposable native GUI fixture for the private-desktop containment proof.

This deliberately contains no network code, file browser or command launcher.
"""
from pathlib import Path
import tkinter as tk

EXPECTED = "kingdom-private-control-ok"
PROOF = Path("/tmp/private-desktop-confirmation.txt")

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
root.after(250, entry.focus_force)
root.mainloop()
