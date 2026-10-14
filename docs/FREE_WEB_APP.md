# Free Kingdom web app installation

Use a reachable HTTPS Kingdom server. On the login screen, choose **Install Kingdom web app** when the browser offers it, or use Edge/Chrome's menu to install the site as an app. The browser displays its own confirmation. Declining does not install the app; the website remains usable. Browser support and install prompts vary.

This is a web app in its own window. Your server and approved cluster computers execute the work. It does not bundle a local Windows backend or make a disconnected server work offline. No payment, self-signed certificate, trusted-root change or lowered Windows protection is needed. The service worker uses the network directly and does not cache private API responses or credentials.

Self-signing is a separate testing technique. New-SelfSignedCertificate creates a certificate; it does not sign a binary. Creating a different key on each recipient's computer cannot authenticate a previously downloaded installer. Adding a self-signed root does not put its issuer into Microsoft's Trusted Root Program and does not solve Smart App Control enforcement. An installer blocked before startup cannot display its own consent prompt. Keep native public signing separate from this free web route.

References: https://learn.microsoft.com/en-us/windows/apps/develop/smart-app-control/overview and https://learn.microsoft.com/windows/msix/package/create-certificate-package-signing . Do not advertise browser installation as a signed native Windows package.
