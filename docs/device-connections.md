# Connect a phone or another device

In Kingdom, open **Devices & Knowledge** or **Nodes & Cluster → Connect a phone / device**. Select **Create connection code**. Codes are single-use and expire after five minutes.

For a phone, enter the HTTPS address of your Kingdom server that the phone can reach. Scan the displayed QR with the phone camera. Alternatively open `https://YOUR-KINGDOM/#/connect` on the device and enter the connection code and device name. QR generation happens locally; no third-party QR service receives the code.

The device generates a real Ed25519 key and signs the connection request. Check the device name and fingerprint in **Nodes & Cluster → Pending Approvals**, then approve or reject it. The browser companion can check its own approval status; it cannot use owner APIs, run tasks, or bypass governance. Sessions expire after 24 hours or a Kingdom restart. Revoke a device in Nodes & Cluster to invalidate its access.

The desktop default is loopback-only. A phone cannot reach `localhost` on your PC, so Kingdom deliberately does not display a misleading localhost QR. Use an existing trusted HTTPS Kingdom deployment/reverse proxy reachable from both devices. Serve the UI and API at the same HTTPS origin, preserve Authorization headers, and configure `ALLOWED_ORIGINS` for that origin. Do not publish the owner access code or disable authentication. This change does not open firewall ports or expose the desktop server automatically.

Modern browsers supporting Web Crypto Ed25519 are required. Unsupported browsers show an error. Native Android/iOS installers are not shipped. The companion is an actual browser pairing/status flow, not a claim of mobile task, voice, upload, or approval execution.

Compute workers use a separate **Add Knight / Pair Node** invitation and the real `backend.cluster.knight_daemon` enrollment process. The former web form with a hard-coded public identity has been removed; a browser companion is not a compute worker.
