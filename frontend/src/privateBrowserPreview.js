/** Client-side preflight only. Server policy and approved task grants are authoritative. */
export function privateBrowserPreviewTask(value) {
  if (typeof value !== 'string' || value.length > 2048) {
    throw new Error('Enter a short HTTPS website address.');
  }
  let parsed;
  try { parsed = new URL(value.trim()); }
  catch { throw new Error('Enter a complete HTTPS website address.'); }
  if (parsed.protocol !== 'https:' || parsed.username || parsed.password ||
      (parsed.port && parsed.port !== '443') || parsed.hash || !parsed.hostname.includes('.')) {
    throw new Error('Choose an HTTPS website without embedded credentials or a fragment.');
  }
  const hostname = parsed.hostname.toLowerCase();
  if (hostname === 'localhost' || hostname.endsWith('.localhost') ||
      /^\d+(?:\.\d+){3}$/.test(hostname) || hostname.includes('*')) {
    throw new Error('Private browser preview cannot open local or IP-only addresses.');
  }
  return {
    prompt: 'Preview approved website in a separate headless browser (read-only network, no host input)',
    metadata: {
      tool: 'computer.browser.run@1.0.0',
      tool_parameters: {
        start_url: parsed.href,
        allowed_hosts: [hostname],
        actions: [],
      },
    },
  };
}
