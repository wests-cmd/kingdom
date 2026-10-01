# Kingdom appearance and artwork

The crowned K and citadel are derived from the user's ChatGPT Library image **Neon Purple Kingdom Citadel**, in **Branch · Branch · Branch · Branch · Branch · Branch · Branch · Build Skills Improve Kingdom**. The source contains painted desktop shortcuts and a taskbar; those are removed from the application assets.

## Saved assets

- `frontend/public/branding/kingdom-icon.png`: transparent 512px crowned K; sidebar and favicon.
- `frontend/public/branding/kingdom-citadel.webp`: clean castle atmosphere.
- `desktop/branding/kingdom-icon.png`: native window icon.
- `desktop/branding/kingdom.ico`: Windows executable/installer/desktop shortcut.
- `desktop/branding/kingdom.icns`: macOS app icon. Linux uses the PNG.

Generated with the built-in image editor from the exact source image. Pillow only resized and encoded native icon formats. No newly invented identity was substituted.

## Prompts used

Icon: Use case: background-extraction. Image 1 is the edit target, the user's existing Kingdom artwork. Extract only the large crowned K emblem on the right, preserving that exact purple gemstone, black metal crown, gothic K silhouette and highlights. Remove all castle scenery, desktop shortcuts, taskbar, word KINGDOM, and background. Center the single emblem in a square canvas with modest padding; actual transparent background and clean alpha edges, suitable for a desktop application icon at 32px through 512px. Do not invent a new logo; retain this crowned K identity. No other text or elements.

Background: Use case: precise-object-edit. Image 1 is the edit target: user's Neon Purple Kingdom Citadel artwork. Make a clean wide application background from this exact castle scenery. Keep the castle architecture, purple moon, black rock cliffs, violet cloud lighting and overall dramatic purple-and-black mood. Remove all painted desktop shortcut icons and labels along the left edge, the full Windows taskbar across the bottom, and the large crowned K/Kingdom wordmark on the right, filling those regions naturally with matching scenery/clouds. No desktop UI, text, logo, icons or watermarks. Do not add other structures or characters. Wide landscape wallpaper, suitable behind real readable app controls.

## Settings

Settings now applies five palettes or a custom accent, dark/light/device mode, comfortable/compact spacing, 90–125% display size, reduced motion and 0–20% background atmosphere. Reset restores royal purple. Preferences are validated and stored under `kingdom.appearance.v1` in this installation's localStorage. They apply before rendering and survive reload; unavailable storage is reported honestly. Preferences do not change runtime authority or sync between devices. Semantic status colors remain independent, and custom accent text/primary buttons adjust for contrast.

Browser checks cover the loaded logo, light/jade mode, spacing, display size, motion, atmosphere, reload persistence, reset and a 390px phone viewport. Native release checks load the actual logo, change light mode, reload, verify persistence and reset on each target OS. Frozen backend checks verify both bundled image endpoints. Screenshots and platform evidence accompany the release verification report.
