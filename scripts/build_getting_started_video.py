#!/usr/bin/env python3
"""Illustrated narrated Kingdom onboarding video for the public v1.2.4 README.

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
    ("HERE'S THE GITHUB PAGE", "Welcome to Kingdom", "You just arrived at the repository",
     ["github.com/wests-cmd/kingdom", "Look for Releases or scroll to the README",
      "Use the published installer — not Code → Download ZIP"],
     "You have just arrived at github dot com slash wests dash c m d slash kingdom. To install the Kingdom desktop app, find Releases or the install section in the Read Me. Code Download ZIP contains developer source files."),
    ("STEP 1  /  README", "Find the desktop download", "Match your operating system",
     ["Windows 64-bit — Kingdom-Setup-1.2.4.exe",
      "Intel Mac — Kingdom-1.2.4.dmg",
      "Linux 64-bit — Kingdom-1.2.4.AppImage",
      "Debian or Ubuntu — kingdom-desktop_1.2.4_amd64.deb"],
     "On the Read Me page, scroll to Install the desktop app. Select the exact file for your computer. The current published version in this tutorial is one point two point four."),
    ("STEP 2  /  RELEASES", "Open the published release", "Releases → v1.2.4 → Assets",
     ["Choose one platform-specific installer",
      "Files are labeled for Windows, Intel Mac and Linux",
      "SHA256SUMS contains published file checksums"],
     "You can also click Releases, open version one point two point four, and expand Assets. Download only the package that matches your operating system. Do not mistake the repository ZIP for the installer."),
    ("STEP 3  /  INSTALL", "Open the downloaded package", "Follow normal operating-system steps",
     ["Windows: start the Setup executable",
      "Intel Mac: open the DMG package",
      "Linux: use the AppImage or the Debian package",
      "IMPORTANT: the published packages are unsigned"],
     "Open the package and follow your normal operating system installation process. These packages are unsigned, and the Intel Mac version is not notarized. Respect security warnings and do not disable system protection just to install."),
    ("STEP 4  /  FIRST RUN", "Launch the Kingdom app", "Use the native desktop window",
     ["Complete first-run setup", "Choose a profile",
      "Opening passcode: optional and off by default",
      "Keep your owner code private"],
     "Open Kingdom from your applications. Complete the first time setup and choose a profile. Its local opening passcode starts off. Do not share your owner access code."),
    ("STEP 5  /  MODELS", "Connect a model if needed", "Routing → save and test your model profile",
     ["Choose a supported configured model provider",
      "Verify the provider connection before using AI generation",
      "Built-in Analyze text is a simpler first task"],
     "If you want AI-generated answers, visit Routing, configure a provider and test its connection. A saved profile alone does not mean that an AI model is available."),
    ("STEP 6  /  RUNTIME", "Start Runtime", "This enables authorized queued tasks",
     ["Open Runtime, switching to advanced view if needed",
      "Select Start Runtime",
      "Starting does NOT grant computer permissions"],
     "Open Runtime. If you cannot see it, switch to the advanced interface under Settings. Select Start Runtime. This does not automatically approve new computer tools."),
    ("STEP 7  /  TASKS", "Try Analyze text", "Your first simple task",
     ["Go to Tasks and choose Analyze text",
      "Enter a short paragraph or request",
      "Submit, then read the actual result"],
     "Open Tasks, choose Analyze text, and enter a small sample. For example, ask for a paragraph summary or a few action items. Submit the task and look at the returned result."),
    ("STEP 8  /  RESULTS", "Confirm the task finished", "Check status and verification",
     ["Queued is not completed",
      "Waiting for approval needs your decision",
      "Inspect task result and verification evidence"],
     "Check the task status and real result. Queued, connected, or suggested does not mean completed. Sensitive actions may stop until you review and approve them."),
    ("OPTIONAL  /  NODES", "Connect another computer", "Trust and permissions stay separate",
     ["Nodes & Cluster → create a single-use invitation",
      "Review the computer identity and fingerprint",
      "Approve only necessary capabilities"],
     "To add another computer, open Nodes and Cluster. Create a single use pairing code, check the computer fingerprint, and explicitly approve the capabilities you trust."),
    ("NEXT STEPS", "Explore Kingdom safely", "README • Documentation • Releases • Issues",
     ["Check Settings for Windows desktop updates",
      "Mac and Linux use their matching native packages",
      "Check release notes and project status before updating",
      "Get help on the GitHub Issues page"],
     "For updates, check Settings or the published release page. Windows desktop updates are available from Settings, while Mac and Linux use matching installers. Explore the documentation and GitHub Issues for help."),
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
    txt(d, (219, 208), "https://" + BASE if i <= 2 or i == 10 else "Kingdom native desktop app", 18, MUTED)
    txt(d, (101, 268), category, 19, BLUE, True)
    width = 1047
    for n, item in enumerate(items):
        y = 318 + n * (61 if len(items) == 4 else 76)
        rounded(d, (111, y, 1155, y+53), (41, 62, 86) if n == 0 else CARD,
                BLUE if n == 0 else (65, 82, 107), 11)
        txt(d, (136, y + 13), item, 21, INK if n == 0 else MUTED, n == 0)
    rounded(d, (50, 620, 1230, 676), (25, 35, 50), (63, 78, 96), 10)
    txt(d, (77, 633), "Illustrated walkthrough • published v1.2.4 • not live footage", 17, MUTED)
    txt(d, (1060, 633), f"{i+1:02d} / {len(SCENES):02d}", 18, BLUE, True)
    d.rectangle((0, 701, W, 720), fill=(31, 44, 63))
    d.rectangle((0, 701, W*(i+1)//len(SCENES), 720), fill=BLUE)
    return canvas

def cmd(args):
    subprocess.run(args, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

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
                 f"fade=t=in:st=0:d=.2,fade=t=out:st={seconds-.25:.3f}:d=.25,format=yuv420p",
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
