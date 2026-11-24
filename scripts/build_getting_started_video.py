#!/usr/bin/env python3
"""Illustrated narrated Kingdom onboarding video for the published v1.2.6 desktop release.

Reproducible from tracked source. Does not claim live UI footage or launch
Kingdom, install executables, read credentials, or make network requests.
Requires Pillow, ffmpeg, ffprobe and espeak (for narration).
"""
import argparse
import shutil
import subprocess
import tempfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

W, H = 1280, 720
BG = (12, 17, 29)
CARD = (31, 43, 62)
BLUE = (79, 159, 246)
INK = (244, 247, 251)
MUTED = (168, 184, 202)
RED = (228, 96, 107)
GREEN = (107, 215, 159)
BASE = "github.com/wests-cmd/kingdom"

SCENES = [
    ("OPEN GITHUB", "Install Kingdom without coding", "Start on the repository README",
     ["github.com/wests-cmd/kingdom",
      "Click Releases or an installer link in the README",
      "Do NOT click Code > Download ZIP: that is source code"],
     "Open github dot com slash wests dash c m d slash kingdom. You do not need to write code or open a terminal. Click Releases, or scroll to the install links in the Read Me. Avoid Code Download ZIP: that is the source, not the desktop installer."),
    ("CHOOSE YOUR SYSTEM", "Pick ONE matching installer", "Published release v1.2.6",
     ["Windows x64: Kingdom-Setup-1.2.6.exe",
      "Intel Mac: Kingdom-1.2.6.dmg",
      "Linux x64: Kingdom-1.2.6.AppImage",
      "Debian or Ubuntu x64: kingdom-desktop_1.2.6_amd64.deb"],
     "Choose one installer for your computer. Windows uses the Setup E X E. Intel Mac uses the D M G. Linux uses the AppImage; Debian and Ubuntu users can use the D E B. These published packages include Kingdom's local runtime."),
    ("RELEASES / ASSETS", "Download from the release", "Select v1.2.6 > Assets",
     ["Open Releases and find v1.2.6",
      "Under Assets, click the matching installer",
      "Use SHA256SUMS to check your download if needed"],
     "If you opened Releases, select version one point two point six and find Assets. Download only the matching installer. SHA two five six sums provides checksums if you want to verify the file."),
    ("INSTALL ON DESKTOP", "Open the downloaded package", "No Python, Node or Docker setup",
     ["Windows: run Setup and follow the installer",
      "Intel Mac: open the DMG and install the app",
      "Linux: open AppImage, or install the DEB package",
      "Packages are unsigned; respect OS security warnings"],
     "Open your downloaded package and follow the normal system instructions. This desktop release does not require a separate Python, Node, or Docker installation. Windows and Mac packages are unsigned, and Mac is not notarized. Respect your computer's security controls; do not disable them to continue."),
    ("FIRST LAUNCH", "Open the Kingdom desktop app", "Complete the guided setup",
     ["Choose a profile suited to your computer",
      "Kingdom opens in its own desktop window",
      "Local opening passcode starts disabled",
      "Keep the owner access code private"],
     "Launch Kingdom from your applications. Follow the setup wizard and choose a profile that matches your computer. Kingdom opens in its own desktop window. The optional local opening passcode starts off. Keep the private owner access code secret."),
    ("FIRST TASK / NO MODEL", "Start with built-in analysis", "You can test Kingdom before adding AI",
     ["Open Runtime and select Start Runtime",
      "If Runtime is hidden, use advanced view in Settings",
      "Open Tasks and select Analyze text",
      "Paste a short paragraph and submit"],
     "You can test the basic built-in tools without downloading a model. Open Runtime and choose Start Runtime. If you cannot find it, choose the advanced view in Settings. Then open Tasks, select Analyze text, paste a short paragraph, and submit."),
    ("VERIFY RESULT", "Check the task actually completed", "Status, output and verification",
     ["Completed: inspect the output and verification",
      "Queued means the task has not finished",
      "Waiting approval means you must review it",
      "Starting Runtime never grants extra permissions"],
     "Wait for the task record to say completed, then inspect the actual output and verification. Queued is not finished. Waiting approval means you need to review the request. Starting the Runtime does not grant computer permissions."),
    ("OPTIONAL AI", "Want model-generated answers?", "Configure Routing after the first test",
     ["Open Routing and select a supported provider",
      "Save and test the model connection",
      "An unavailable provider cannot generate answers"],
     "To use model-generated answers, open Routing, select a supported configured provider, and test the connection. This is optional for the first built-in analysis task. A saved model name is not evidence that a model is actually running."),
    ("OPTIONAL COMPUTERS", "Connect another Knight safely", "Pairing is separate from tool approval",
     ["Nodes & Cluster: create a one-use invitation",
      "Check the computer identity and fingerprint",
      "Approve only the capabilities it needs"],
     "To add a computer, open Nodes and Cluster. Create a single use invitation. Check the device identity and fingerprint, then approve only the capabilities it needs. A connected device is not automatically trusted to run sensitive tools."),
    ("UPDATES AND HELP", "You are ready to use Kingdom", "Keep releases and permissions current",
     ["Windows: Settings > Desktop updates",
      "Intel Mac and Linux: use the matching new package",
      "Help: README, documentation and GitHub Issues",
      "This is an illustrated guide, not live screen capture"],
     "For later updates, Windows offers desktop updates in Settings, while Mac and Linux use new published packages. For help, check the Read Me, documentation or GitHub Issues. This video is an illustrated walkthrough, not a recording of the live application.")
]

def font(size, bold=False):
    name = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
    return ImageFont.truetype(name, size)

def txt(draw, pos, value, size=24, color=INK, bold=False):
    draw.text(pos, value, font=font(size, bold), fill=color)

def rounded(draw, coords, fill=CARD, border=None, radius=16):
    draw.rounded_rectangle(coords, radius=radius, fill=fill, outline=border)

def slide(i, scene):
    category, title, subtitle, items, speech = scene
    canvas = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(canvas)
    d.rectangle((0, 0, W, 9), fill=RED)
    txt(d, (70, 36), "KINGDOM   /   GETTING STARTED", 19, BLUE, True)
    txt(d, (70, 88), title, 44, INK, True)
    txt(d, (72, 149), subtitle, 21, MUTED)
    rounded(d, (69, 194, 1211, 604), (17, 24, 37), (79, 94, 117), 20)
    rounded(d, (69, 194, 1211, 244), (42, 53, 70), None, 20)
    d.rectangle((70, 221, 1210, 246), fill=(42, 53, 70))
    for x, c in ((98, RED), (123, (236, 184, 91)), (148, GREEN)):
        d.ellipse((x, 208, x+13, 221), fill=c)
    rounded(d, (197, 204, 1127, 235), (18, 25, 38), (78, 93, 115), 9)
    txt(d, (219, 208), "https://" + BASE if i <= 2 or i == len(SCENES)-1 else "Kingdom native desktop app", 18, MUTED)
    txt(d, (101, 268), category, 19, BLUE, True)
    width = 1047
    for n, item in enumerate(items):
        y = 318 + n * (61 if len(items) == 4 else 76)
        rounded(d, (111, y, 1155, y+53), (41, 62, 86) if n == 0 else CARD,
                BLUE if n == 0 else (65, 82, 107), 11)
        txt(d, (136, y + 13), item, 21, INK if n == 0 else MUTED, n == 0)
    rounded(d, (50, 620, 1230, 676), (25, 35, 50), (63, 78, 96), 10)
    txt(d, (77, 633), "Illustrated walkthrough • published v1.2.6 • not live footage", 17, MUTED)
    txt(d, (1060, 633), f"{i+1:02d} / {len(SCENES):02d}", 18, BLUE, True)
    d.rectangle((0, 701, W, 720), fill=(31, 44, 63))
    d.rectangle((0, 701, W*(i+1)//len(SCENES), 720), fill=BLUE)
    return canvas

def cmd(args):
    try:
        subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as error:
        # CI should expose the actual encoder/filter failure instead of a
        # traceback with only the exit code.
        print(error.stderr.decode("utf-8", errors="replace")[-6000:])
        raise

def clip_length(path):
    return float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)], text=True).strip())

def create(out):
    if not shutil.which("ffmpeg") or not shutil.which("espeak"):
        raise RuntimeError("ffmpeg and espeak required; install via Ubuntu apt")
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="kingdom-guide-") as dirname:
        work = Path(dirname)
        videos, frames = [], []
        for i, scene in enumerate(SCENES):
            img = slide(i, scene)
            frame = work / f"frame-{i:02d}.png"
            img.save(frame, optimize=True)
            if i in (0, 1, 2, 4):
                frames.append(img.resize((800, 450), Image.Resampling.LANCZOS).quantize(colors=48))
            voice = work / f"narration-{i:02d}.wav"
            cmd(["espeak", "-v", "en-us", "-s", "155", "-a", "155", "-w", str(voice), scene[4]])
            seconds = clip_length(voice) + .5
            segment = work / f"segment-{i:02d}.mp4"
            cmd(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                 "-loop", "1", "-framerate", "24", "-i", str(frame), "-i", str(voice),
                 "-t", f"{seconds:.3f}", "-vf",
                 f"fade=t=in:st=0:d=0.2,fade=t=out:st={seconds-0.25:.3f}:d=0.25,format=yuv420p",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "27",
                 "-r", "24", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "96k",
                 str(segment)])
            videos.append(segment)
        sources = work / "concat.txt"
        sources.write_text("".join("file '" + str(video) + "'\n" for video in videos),
                           encoding="utf-8")
        cmd(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-f", "concat",
             "-safe", "0", "-i", str(sources), "-c", "copy", "-movflags", "+faststart",
             str(out / "kingdom-getting-started.mp4")])
        frames[0].save(out / "kingdom-getting-started-preview.gif", save_all=True,
                       append_images=frames[1:], duration=1300, loop=0,
                       optimize=True, disposal=2)
        for file in sorted(out.iterdir()):
            print(f"{file}: {file.stat().st_size} bytes")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=Path("docs/media"))
    create(parser.parse_args().output_dir)
