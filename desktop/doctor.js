/**
 * KINGDOM Doctor — Self-Diagnostic Engine
 * Performs real system resource inspection and queries local Kingdom backend diagnostic scan.
 */

const os = require('os');
const http = require('http');

function fetchBackendScan(port = 8000) {
  return new Promise((resolve) => {
    http.get(`http://localhost:${port}/diagnostics/full-scan`, (res) => {
      let body = '';
      res.on('data', (chunk) => body += chunk);
      res.on('end', () => {
        try {
          resolve(JSON.parse(body));
        } catch {
          resolve(null);
        }
      });
    }).on('error', () => {
      resolve(null);
    });
  });
}

async function runDoctorDiagnostics() {
  const cpus = os.cpus();
  const totalMem = os.totalmem();
  const freeMem = os.freemem();

  const backendReport = await fetchBackendScan();

  const report = {
    timestamp: new Date().toISOString(),
    system: {
      platform: os.platform(),
      arch: os.arch(),
      cpu_cores: cpus.length,
      memory_total_gb: (totalMem / (1024 ** 3)).toFixed(2),
      memory_free_gb: (freeMem / (1024 ** 3)).toFixed(2)
    },
    status: backendReport ? backendReport.status : "UNAVAILABLE",
    backend_diagnostics: backendReport || { error: "Backend diagnostic endpoint unreachable" }
  };

  return report;
}

if (require.main === module) {
  runDoctorDiagnostics().then((res) => console.log(JSON.stringify(res, null, 2)));
}

module.exports = { runDoctorDiagnostics };
