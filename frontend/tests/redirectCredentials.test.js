import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import vm from 'node:vm';
import followRedirects from 'follow-redirects';

// A caller-supplied sensitive header must not cross an origin redirect,
// including when the sensitiveHeaders list came from another JS realm.
test('cross-realm sensitive headers are stripped while harmless headers survive', { timeout: 5000 }, async () => {
  let received;
  const target = http.createServer((req, res) => { received = req.headers; res.end('ok'); });
  const listen = server => new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const close = server => new Promise(resolve => server.close(resolve));
  await listen(target);
  const redirect = http.createServer((req, res) => {
    res.writeHead(302, { Location: `http://127.0.0.1:${target.address().port}/` }); res.end();
  });
  try {
    await listen(redirect);
    await new Promise((resolve, reject) => {
      const request = followRedirects.http.get(`http://127.0.0.1:${redirect.address().port}/`, {
        sensitiveHeaders: vm.runInNewContext("['X-Test-Secret']"),
        headers: { 'X-Test-Secret': 'test-only-not-a-real-credential', 'X-Harmless': 'keep' },
      }, response => { response.resume(); response.on('end', resolve); });
      request.setTimeout(2000, () => request.destroy(new Error('Loopback redirect timeout')));
      request.on('error', reject);
    });
    assert.equal(received['x-test-secret'], undefined);
    assert.equal(received['x-harmless'], 'keep');
  } finally { await close(redirect); await close(target); }
});
