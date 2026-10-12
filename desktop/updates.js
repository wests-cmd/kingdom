// Owner-initiated Windows upgrades. User data lives outside the application directory.
const https = require('https');
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { pipeline } = require('stream/promises');
const { Transform } = require('stream');
const { spawn } = require('child_process');
const RELEASES = 'https://api.github.com/repos/wests-cmd/kingdom/releases/latest';
const HOSTS = new Set(['api.github.com', 'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com']);
const MAX_INSTALLER = 512 * 1024 * 1024;

function version(value) {
  if (!/^\d+\.\d+\.\d+$/.test(value)) throw new Error('Unsupported release version');
  return value.split('.').map(Number);
}
function newer(a, b) {
  const x = version(a), y = version(b);
  for (let i = 0; i < 3; i++) if (x[i] !== y[i]) return x[i] > y[i];
  return false;
}
function candidate(release, current) {
  const latest = String(release.tag_name || '').replace(/^v/, '');
  version(latest);
  if (release.draft || release.prerelease) throw new Error('Only published stable releases can be installed');
  if (!newer(latest, current)) return { available: false, current, latest };
  const name = `Kingdom-Setup-${latest}.exe`;
  const asset = release.assets?.find(item => item.name === name);
  const url = `https://github.com/wests-cmd/kingdom/releases/download/v${latest}/${name}`;
  if (!asset || asset.browser_download_url !== url || !/^sha256:[a-f0-9]{64}$/.test(asset.digest || '') ||
      !Number.isSafeInteger(asset.size) || asset.size <= 0 || asset.size > MAX_INSTALLER) {
    throw new Error('Release has no checksum-verified Windows installer');
  }
  return { available: true, current, latest, name, url, size: asset.size, sha256: asset.digest.slice(7) };
}
function request(url, redirects = 0) {
  const target = new URL(url);
  if (target.protocol !== 'https:' || !HOSTS.has(target.hostname) || target.username || target.password || redirects > 5) {
    return Promise.reject(new Error('Untrusted update download'));
  }
  return new Promise((resolve, reject) => {
    const req = https.get(target, { headers: { 'User-Agent': 'Kingdom-desktop-updates', Accept: 'application/vnd.github+json' } }, res => {
      if ([301, 302, 303, 307, 308].includes(res.statusCode)) {
        res.resume();
        request(new URL(res.headers.location, target).href, redirects + 1).then(resolve, reject);
      } else if (res.statusCode === 200) resolve(res);
      else { res.resume(); reject(new Error(`Update server returned HTTP ${res.statusCode}`)); }
    });
    req.setTimeout(30000, () => req.destroy(new Error('Update download timed out')));
    req.on('error', reject);
  });
}
async function verifyFile(file, update) {
  if (fs.statSync(file).size !== update.size) throw new Error('Downloaded installer size differs');
  const digest = crypto.createHash('sha256');
  for await (const chunk of fs.createReadStream(file)) digest.update(chunk);
  if (digest.digest('hex') !== update.sha256) throw new Error('Downloaded installer checksum differs');
}
function handoffScript(pid, installer, executable, digest, latest, receipt) {
  const quote = text => "'" + text.replace(/'/g, "''") + "'";
  if (!Number.isSafeInteger(pid) || pid <= 0) throw new Error('Invalid process identity');
  version(latest);
  return `$ErrorActionPreference='Stop'\ntry {\n` +
    `if (Get-Process -Id ${pid} -ErrorAction SilentlyContinue) { Wait-Process -Id ${pid} -Timeout 90 }\n` +
    `if ((Get-FileHash -LiteralPath ${quote(installer)} -Algorithm SHA256).Hash.ToLowerInvariant() -ne ${quote(digest)}) { throw 'Installer checksum changed' }\n` +
    `$result=Start-Process -FilePath ${quote(installer)} -ArgumentList @('/S',${quote('/D=' + path.dirname(executable))}) -WindowStyle Hidden -Wait -PassThru\n` +
    `$result.WaitForExit();$result.Refresh()\n` +
    `if ($null -ne $result.ExitCode -and $result.ExitCode -ne 0) { throw 'Kingdom upgrade failed' }\n` +
    `$deadline=(Get-Date).AddSeconds(90)\n` +
    `do { $installed=if(Test-Path -LiteralPath ${quote(executable)}){(Get-Item -LiteralPath ${quote(executable)}).VersionInfo.ProductVersion}else{''}; if($installed -eq ${quote(latest)} -or $installed -eq ${quote(latest + '.0')}){break}; Start-Sleep -Seconds 1 } while((Get-Date) -lt $deadline)\n` +
    `if($installed -ne ${quote(latest)} -and $installed -ne ${quote(latest + '.0')}){throw 'Installed version could not be verified'}\n` +
    `@{success=$true;version=${quote(latest)}} | ConvertTo-Json | Set-Content -LiteralPath ${quote(receipt)} -Encoding UTF8\n` +
    `Remove-Item -LiteralPath ${quote(installer)} -ErrorAction SilentlyContinue\n` +
    `} catch { @{success=$false;version=${quote(latest)};message='The upgrade could not finish. Your data is retained. Retry the update.'} | ConvertTo-Json | Set-Content -LiteralPath ${quote(receipt)} -Encoding UTF8 } finally { if(Test-Path -LiteralPath ${quote(executable)}){Start-Process -FilePath ${quote(executable)}} }\n`;
}
class DesktopUpdates {
  constructor(app) {
    this.app = app; this.ready = null; this.busy = false; this.installing = false;
    this.directory = path.join(app.getPath('userData'), 'updates');
    try {
      const saved = JSON.parse(fs.readFileSync(path.join(this.directory, 'ready.json'), 'utf8'));
      const update = candidate({tag_name: `v${saved.latest}`, assets: [{name: saved.name, browser_download_url: saved.url, size: saved.size, digest: `sha256:${saved.sha256}`}]}, app.getVersion());
      if (update.available && fs.existsSync(path.join(this.directory, update.name))) this.ready = { update, file: path.join(this.directory, update.name) };
    } catch { /* Missing or invalid cache is never executable. */ }
  }
  status() {
    let previous = null;
    try { const result = JSON.parse(fs.readFileSync(path.join(this.directory, 'result.json'), 'utf8').replace(/^\uFEFF/, ''));
      if (typeof result.success === 'boolean') previous = { success: result.success, message: result.success ? 'The previous desktop upgrade completed.' : 'The previous upgrade could not finish. Your data is retained; download and retry the update.' };
    } catch { /* No previous attempt. */ }
    return { current: this.app.getVersion(), supported: process.platform === 'win32' && this.app.isPackaged,
      ready: this.ready ? { latest: this.ready.update.latest } : null, previous };
  }
  async check() {
    if (!this.status().supported) return { ...this.status(), available: false, reason: 'Native in-app upgrades currently support installed Windows desktops. Compatible UI updates work separately below.' };
    const response = await request(RELEASES); let bytes = 0, chunks = [];
    for await (const chunk of response) { bytes += chunk.length; if (bytes > 2 * 1024 * 1024) { response.destroy(); throw new Error('Release metadata exceeds limits'); } chunks.push(chunk); }
    return candidate(JSON.parse(Buffer.concat(chunks)), this.app.getVersion());
  }
  async download() {
    if (this.busy) throw new Error('An update download is already running');
    this.busy = true;
    let temporary;
    try {
      const update = await this.check();
      if (!update.available) throw new Error('No newer Windows release is available');
      const directory = this.directory; fs.mkdirSync(directory, { recursive: true });
      const file = path.join(directory, update.name); temporary = file + '.part';
      const response = await request(update.url); let bytes = 0;
      const bound = new Transform({ transform(chunk, encoding, callback) { bytes += chunk.length; callback(bytes > update.size ? new Error('Installer exceeds its published size') : null, chunk); } });
      await pipeline(response, bound, fs.createWriteStream(temporary, { mode: 0o600 }));
      await verifyFile(temporary, update); fs.renameSync(temporary, file);
      fs.writeFileSync(path.join(directory, 'ready.json'), JSON.stringify(update), { mode: 0o600 });
      this.ready = { update, file }; return this.status();
    } finally { this.busy = false; if (temporary && fs.existsSync(temporary)) fs.unlinkSync(temporary); }
  }
  async install() {
    if (this.installing || this.busy) throw new Error('An update operation is already running');
    if (!this.status().supported || !this.ready) throw new Error('Download and verify an update first');
    this.installing = true;
    try {
    await verifyFile(this.ready.file, this.ready.update);
    const script = handoffScript(process.pid, this.ready.file, this.app.getPath('exe'), this.ready.update.sha256, this.ready.update.latest, path.join(this.directory, 'result.json'));
    const helper = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-EncodedCommand', Buffer.from(script, 'utf16le').toString('base64')], { detached: true, windowsHide: true, stdio: 'ignore' });
    await new Promise((resolve, reject) => { helper.once('spawn', resolve); helper.once('error', reject); });
    helper.unref(); this.app.quit(); return { restarting: true };
    } catch (error) { this.installing = false; throw error; }
  }
}
module.exports = { DesktopUpdates, candidate, newer, verifyFile, handoffScript };
