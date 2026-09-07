# STEP 6 ARCHITECTURE: ONE-COMMAND DESKTOP INSTALLATION & DISTRIBUTION

Kingdom supports cross-platform desktop installer packaging via `desktop/package.json` and `electron-builder`.

## Target Installer Artifacts
- **Windows**: `Kingdom-Setup.exe` (NSIS Installer)
- **macOS**: `Kingdom.dmg`
- **Linux**: `Kingdom.AppImage`, `Kingdom.deb`

## One-Command Developer Installation
```bash
./scripts/install.sh
```
OR
```bash
npm --prefix desktop run build
```
Users download and run the platform-specific desktop installer wrapper without manually setting up Python or Node.
