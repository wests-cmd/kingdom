/**
 * KINGDOM Desktop Hardware Detection Engine
 * Performs safe, lightweight hardware inspection using built-in Node.js APIs.
 */

const os = require('os');

function detectGpu() {
  try {
    if (process.env.GPU_MODEL) {
      return {
        present: true,
        name: String(process.env.GPU_MODEL)
      };
    }
  } catch (err) {
    // Ignore any error and fall back cleanly
  }

  return {
    present: false,
    name: null
  };
}

function detectDisplay(platform) {
  if (platform === 'linux') {
    return Boolean(process.env.DISPLAY || process.env.WAYLAND_DISPLAY);
  }
  return true;
}

function getHardwareReport() {
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
  const cpuModel = cpus[0] && cpus[0].model ? cpus[0].model.trim() : 'Unknown CPU';
  const memoryTotalGb = Math.round((totalMem / (1024 * 1024 * 1024)) * 10) / 10;
  const gpuInfo = detectGpu();
  const hasDisplay = detectDisplay(platform);

  return {
    platform,
    arch,
    cpu_cores: cpuCores,
    cpu_model: cpuModel,
    memory_total_gb: memoryTotalGb,
    gpu: gpuInfo,
    has_display: hasDisplay
  };
}

function suggestProfile(report) {
  if (!report || !report.has_display) {
    return 'server_headless';
  }

  if (report.memory_total_gb >= 8 && report.cpu_cores >= 4) {
    return 'full_swarm';
  }

  if (report.memory_total_gb < 4) {
    return 'server_headless';
  }

  return 'developer';
}

module.exports = {
  getHardwareReport,
  suggestProfile
};
