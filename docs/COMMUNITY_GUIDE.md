# Kingdom community FAQ and bot verification

Community invite: https://discord.gg/4b8f9YS2Wp  
Published stable release: https://github.com/wests-cmd/kingdom/releases/tag/v1.1.1

This is public onboarding information for server maintainers and bot knowledge sources. It contains no credentials. The server was inspected with the owner-provided signed-in session. It contains welcome, announcements, kingdom, centipede, ai-skill-map and private bot-knowledge channels. The **Kingdom Centipede Skill Bot** replied to `/commands`. Welcome and release-download information were added to the previously empty welcome and announcements channels.

## Information to make easy to find

Welcome now explains first launch, appearance, support and bot boundaries. Announcements lists the verified v1.1.1 platform installers, checksum/release evidence and limitations. Maintain those existing posts as releases change; avoid duplicate channels and outdated filenames.

Downloads should link to the published installers in the [README](../README.md#download-kingdom), the matching release page and checksums. Avoid attaching unverified builds or presenting source archives as desktop installers. Keep the release version and platform filenames synchronized when a new release is published.

## Answers a support bot should know

| Question | Verified answer / source |
| --- | --- |
| Where do I download Kingdom? | Use the platform installer links at [Download Kingdom](../README.md#download-kingdom). The currently published stable release is v1.1.1. Verify future “latest” answers against [GitHub Releases](https://github.com/wests-cmd/kingdom/releases/latest). |
| Do I need Python or Node? | No for the packaged desktop installers. They bundle the backend and frontend. Source development uses separate dependencies. |
| Which computer is supported? | Windows x86_64 NSIS, Linux x86_64 AppImage/amd64 DEB, and macOS Intel DMG. Native ARM and mobile installers are absent. Windows/macOS are unsigned, and macOS is not notarized. |
| How do I start? | Launch the installer/app, complete the profile wizard, start Runtime, then submit an Analyze text task. The result should be completed and verified. |
| How do I change colors? | Open Settings. Palettes, custom accent/hex, color mode, spacing, display size, reduced motion, atmosphere and reset apply and save on this device. |
| How do I connect my phone? | Use a reachable trusted HTTPS Kingdom address, the single-use code/QR, and owner approval in Pending Approvals. The code expires in five minutes. `localhost` on the phone cannot reach your PC. No native mobile app is shipped. |
| Can it trade or browse arbitrary services? | Broker integration, live market data, trade execution, unrestricted web search and arbitrary uploaded endpoints are unsupported. A generated answer or imported map does not prove an action happened. |
| What is a skill map? | Validated JSON/YAML preferences. Import requires preview and confirmation. It never installs permissions/tools. Export includes canonical JSON and a SHA-256 hash. |
| What providers can be tested? | Explicitly enabled reviewed Open Food Facts and Open-Meteo read-only metadata checks, through authorized workers and independent verification. They are not buying, pricing or full research workflows. |
| Does joining Discord authorize my desktop? | No. `/kingdom` requests a private challenge; the owner links the identity and chooses grants in the app. Discord administrators do not inherit Kingdom privileges. |
| Why doesn't `/status` work? | Check the actual installed bot, command registration, configured guild, owner-confirmed identity and `view_status` grant. Do not fix this by disabling authentication. |
| What should I share for support? | Version, OS/architecture, installation method, exact error and reproducible steps. Remove credentials, owner/linking codes, private documents and personal data. |

The community bot supports `/commands`, `/ask`, `/aiask`, `/skillmap`, `/search`, `/sources`, `/projectinfo`, `/compare`, `/exportknowledge` and `/botstatus`. Private administrator commands are `/teach`, `/history` and `/forget`. Its knowledge supports lookup/local AI drafts, not model retraining or native task execution. Private teaching remains separate from public answers.

The bundled Kingdom runtime adapter is a separate integration. It exposes structured slash commands; it is not a general chat/FAQ language model. This FAQ is documentation for a support bot or maintainers, not a claim that the installed adapter answers arbitrary natural-language questions. `/help` currently lists commands and permissions; consult these documents for installation and release answers.

## Community bot test checklist

Test `/commands`, `/ask` with current download/appearance/phone questions, private `/teach` confirmation and lookup, `/history`, `/botstatus`, and public/private answer separation. An out-of-date or unrelated answer is a failure even if the bot responded. These commands concern the community knowledge bot, not owner-authorized native runtime execution.

## Optional runtime adapter test checklist

Use the server's actual installed bot and a designated test/support channel. Use public sample data. Record the command/question, exact reply, timestamp, result and relevant version; redact identity-linking codes and credentials from screenshots.

1. `/help`: commands and linking instructions appear privately; no credentials or invented state are shown.
2. `/status` before linking: deny access. Discord administrator privileges must not bypass the boundary.
3. `/kingdom`: a private, five-minute challenge is generated. Confirm it in the owner app with `view_status` only. Do not publish the challenge.
4. `/status` after linking: compare running/stopped with the connected Kingdom instance. Check that `/tasks` remains denied without its separate grant.
5. Revoke the identity in the owner app: subsequent authorized-state requests must fail.
6. For a separate support/FAQ bot, ask the questions above. Check download links, platform exclusions, phone instructions, color settings, and unsupported trading against the source documents. Treat missing or invented answers as failures.
7. If map testing is configured, use the documented sample map and explicit grants. Test import/preview/confirmation/export; compare exact canonical checksums. A disabled provider or missing worker must not be reported as a successful test.

A local adapter test can verify routing, signatures, permission checks and delivery handling. It cannot establish that Discord received a real message or that a server's live bot has loaded this FAQ. Mark live delivery **not verified** until actual server replies are observed.
