Kingdom v1TAS (v1.0.0)

Source commit: `source-commit`

Verified native x86_64 installers: Linux AppImage and DEB, Windows NSIS, macOS Intel DMG. Each platform builds its own bundled backend; Python and Node.js are not required on the user's machine.

Every build passes the backend test suite, a frozen backend startup/readiness and frontend check, and a packaged desktop first-run setup/profile persistence/dashboard check that submits a real text-analysis task through the UI and verifies its result. Platform evidence and screenshots are attached. These checks establish the documented release gate; they are not exhaustive hardware compatibility testing.

Administrative APIs and live connections require owner authentication. Worker results are signed and bound to exact active leases. Approvals persist, expire, and can be consumed only once for the exact authorized operation. Supported tasks execute bounded text/Python analysis; AI text generation requires a configured model provider and never proves external actions occurred. Broker connection, live market data, and trade execution are unavailable. Desktop upgrades use these verified installers; automatic in-place desktop upgrades are not provided.

Windows installers are unsigned. The macOS Intel installer is unsigned and not notarized; a native Apple Silicon installer is not supplied. OS trust prompts may apply. No signing or notarization claim is made.

This patch adds the user-selected crowned K desktop icon and purple citadel artwork, with working device-local appearance settings: five palettes, custom accent, light/dark/device color mode, spacing, display size, reduced motion, background intensity and reset. Accent text and buttons adjust contrast automatically. Preferences persist on this browser or desktop installation.

This release adds a restrained interface, live recorded activity, persisted and enforced L0-L3 task autonomy, actual runtime polling modes, and cancellation of pending task approvals. Static sample topology and unsupported autonomy/mode cards are removed.

This release fixes knowledge text ingestion, draft skill teaching, worker identity displays, memory listing, task failure explanations, and log filters/timestamps. Device connections support single-use codes and locally generated QR links to a reachable HTTPS server. Browser companions require owner approval and do not gain owner/task authority; native mobile packages remain unavailable.

Portable JSON/YAML skill maps support strict import, preview, owner confirmation and canonical export with SHA-256. Public APIs is untrusted discovery metadata. Explicitly enabled Open Food Facts and Open-Meteo adapters run bounded read-only checks through permissioned local Knights and independent schema/hash verification. Pricing, unrestricted web search, authenticated provider adapters and arbitrary uploaded endpoints are unsupported. Discord is opt-in and disabled by default; its signed adapter and linking workflow are code-tested, but a live Discord connection has not been verified. Follow docs/DISCORD_SKILLMAPS.md for setup and deployment requirements.

Verify downloaded files with `sha256sum -c SHA256SUMS` (or compare SHA-256 using your platform's tools). Exact filenames, sizes, hashes, platforms, and source commit are recorded in `release-manifest.json`.
