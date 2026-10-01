class KingdomMobileClient {
  #sessionToken;
  constructor(commanderUrl = "http://localhost:8000", {sessionToken} = {}) {
    const url = new URL(commanderUrl);
    if (!['http:', 'https:'].includes(url.protocol) || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Use a plain Kingdom server origin.');
    if (sessionToken && url.protocol !== 'https:' && !['localhost','127.0.0.1','[::1]'].includes(url.hostname)) throw new Error('Device sessions require HTTPS or loopback HTTP.');
    this.commanderUrl = url.origin;
    this.#sessionToken = sessionToken;
  }

  async fetchPairingChallenge() {
    throw new Error('The owner creates pairing codes in Kingdom. Open /#/connect on your device to enter a code or scan its QR.');
  }

  async getCommanderStatus() {
    const response = await fetch(this.commanderUrl + '/api/system/version', {redirect:'error', signal:AbortSignal.timeout(5000)});
    if (!response.ok) throw new Error('Kingdom version request failed.');
    const version = await response.json();
    if (typeof version.version !== 'string') throw new Error('Kingdom returned an unsupported version response.');
    let device = null;
    if (this.#sessionToken) {
      const state = await fetch(this.commanderUrl + '/mobile/session/status', {method:'POST', headers:{Authorization:'Bearer ' + this.#sessionToken},redirect:'error',signal:AbortSignal.timeout(5000)});
      if (!state.ok) throw new Error('Device session expired or access was revoked. Pair again.');
      device = await state.json();
      if (device.success !== true) throw new Error('Device session was not verified.');
    }
    return {version:version.version, device_state:device?.device_state || 'not_connected', session_verified:!!device};
  }
}

module.exports = KingdomMobileClient;

if (require.main === module) {
  const client = new KingdomMobileClient();
  client.getCommanderStatus().then(status => console.log(status)).catch(() => {console.error('Kingdom is unavailable. Start the server or configure its address.');process.exitCode=1;});
}
