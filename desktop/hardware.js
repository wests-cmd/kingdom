const os = require('os');

function detectGpu(gpuStatus = null) {
  if (process.env.GPU_MODEL) {
    return { present: true, name: String(process.env.GPU_MODEL), source: 'environment' };
  }
  if (gpuStatus && typeof gpuStatus === 'object') {
    const values = Object.values(gpuStatus).filter(Boolean).map(String);
    if (values.some((value) => /hardware|enabled/i.test(value))) {
      return { present: true, name: 'Hardware acceleration available', source: 'electron' };
    }
    if (values.length && values.every((value) => /disabled/i.test(value))) {
      return { present: false, name: null, source: 'electron' };
    }
  }
  return { present: null, name: null, source: 'unknown' };
}

function detectDisplay(platform) {
  if (process.env.KINGDOM_HEADLESS === '1') return false;
  if (platform === 'linux') return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
  return platform === 'win32' || platform === 'darwin';
}

function getHardwareReport(gpuStatus = null) {
  let platform = 'unknown';
  let arch = 'unknown';
  let cpus = [];
  let totalMem = 0;
  try {
    platform = os.platform();
    arch = os.arch();
    cpus = os.cpus() || [];
    totalMem = os.totalmem() || 0;
  } catch (err) {
    console.error('[Kingdom Hardware] Failed to gather basic OS metrics:', err);
  }
  const cpuCores = cpus.length || 1;
  const cpuModel = cpus[0]?.model?.trim() || 'Unknown CPU';
  const memoryTotalGb = Math.round((totalMem / (1024 ** 3)) * 10) / 10;
  return {
    platform,
    arch,
    cpu_cores: cpuCores,
    cpu_model: cpuModel,
    memory_total_gb: memoryTotalGb,
    gpu: detectGpu(gpuStatus),
    has_display: detectDisplay(platform)
  };
}

function suggestProfile(report) {
  if (!report || !report.has_display || report.memory_total_gb < 4) return 'server_headless';
  if (report.memory_total_gb >= 8 && report.cpu_cores >= 4) return 'full_swarm';
  return 'developer';
}

module.exports = { getHardwareReport, suggestProfile };