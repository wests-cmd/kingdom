export function connectionUrl(raw) {
  const url = new URL(raw.trim());
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash || url.pathname !== '/') throw new Error('Enter only your Kingdom HTTPS address, such as https://your-computer.your-tailnet.ts.net');
  return `${url.origin}/#/connect`;
}
