# Getting started with Kingdom — narrated video transcript

**Open this link first:** https://github.com/wests-cmd/kingdom

The tutorial shows the published **v1.2.4** installers checked November 19, 2026. Newer source branches are not automatically newer public releases. These frames are explanatory drawings, not a live desktop capture. The real product may have a different layout depending on version or interface mode.

## 1. You're already on the GitHub page
Look for the Releases link on the Kingdom repository or scroll down to the README's **Install the desktop app** section. Avoid **Code → Download ZIP** if you just want to use the installed desktop app; that option is source code.

## 2. Choose the right file for your computer
- Windows Intel/AMD 64-bit: **Kingdom-Setup-1.2.4.exe**.
- macOS Intel: **Kingdom-1.2.4.dmg**.
- Linux Intel/AMD 64-bit: **Kingdom-1.2.4.AppImage**.
- Debian/Ubuntu amd64: **kingdom-desktop_1.2.4_amd64.deb**.

Use https://github.com/wests-cmd/kingdom/releases/tag/v1.2.4 or the installer links in the README. These are real, published release assets; do not substitute unrelated backend executables or the repository's source ZIP.

## 3. Run the native installer
Open the appropriate downloaded package and follow normal instructions for your operating system. Read and respect operating-system security warnings. These particular packages are unsigned, and the macOS release is not notarized. Do not bypass security restrictions simply to proceed.

## 4. First launch
Open Kingdom in its own desktop window, complete first-run setup and choose a profile. The optional **local opening passcode starts disabled**. Your private owner access code and any pairing code must never be shared publicly.

## 5. Configure AI if you want it
Model-generated responses need an actual configured provider. Open **Routing**, select a supported model connection, and save/test it. Basic built-in text analysis is a simpler first task.

## 6. Start the runtime
Open **Runtime** and select **Start Runtime**. If you are using the simple/easy interface and the page is not visible, select the advanced interface under Settings. Runtime scheduling does not grant unapproved computer tools.

## 7. Run your first task
Open **Tasks**, choose **Analyze text**, enter a paragraph, submit it, and inspect the returned task status and result. A model response, queued task or connected device alone does not prove execution succeeded.

## 8. Optional: add another computer
In **Nodes & Cluster**, create a single-use pairing invitation, review the device identity and fingerprint, then approve only necessary capabilities. Pairing is not automatic authorization.

## 9. Updates and help
Windows v1.2.1+ has **Settings → Desktop updates**; on macOS/Linux use matching native packages. Always check the latest published release notes and source-versus-installed security status. For help, see the [documentation index](README.md), [release notes](releases/v1.2.4.md), [project status](PROJECT_STATUS.md), or [GitHub Issues](https://github.com/wests-cmd/kingdom/issues). Windows/macOS installers are unsigned; the v1.2.4 release is not a Play Store or App Store release.

## Video build

The source for the video is in [scripts/build_getting_started_video.py](../scripts/build_getting_started_video.py). [The associated workflow](../.github/workflows/getting-started-video.yml) generates the MP4 and animated README preview. It uses local illustration, caption text, and speech synthesis, and never downloads user secrets or signs installers.
