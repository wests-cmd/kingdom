/**
 * KINGDOM Best-Effort Hardware Detection Utility for Desktop Setup Wizard
 */

const os = require('os');
const { execSync } = require('child_process');

function detectGpu() {
  const platform = os.platform();
  try {
    if (platform === 'linux') {
      const output = execSync('lspci 2>/dev/null | grep -i "vga\\|3d\\|display"', { timeout: 2000, encoding: 'utf-8' });
      if (output.strip ? output.strip() : output.trim()) {
        const line = output.split('\n')[0];
        const name = line.split(':').pop().trim();
        return { present: true, name: name || 'Linux Display Adapter' };
      }
    } else if (platform === 'darwin') {
      const output = execSync('system_profiler SPDisplaysDataType 2>/dev/null | grep "Chipset Model"', { timeout: 2000, encoding: 'utf-8' });
      if (output.trim()) {
        const name = output.split(':').pop().trim();
        return { present: true, name: name || 'Apple Display Adapter' };
      }
    } else if (platform === 'win32') {
      const output = execSync('wmic path win32_VideoController get name 2>NUL', { timeout: 2000, encoding: 'utf-8' });
      const lines = output.split('\n').map(l => l.trim()).filter(l => l && l !== 'Name');
      if (lines.length > 0) {
        return { present: true, name: lines[0] };
      }
    }
  } catch (e) {
    // Optional GPU detection safely falls back if command is missing or errors
  }
  return { present: false, name: null };
}

function getHardwareReport() {
  try {
    const cpus = os.cpus() || [];
    const memoryTotalBytes = os.totalmem() || 0;
    const memory_total_gb = Math.round((memoryTotalBytes / (1024 * 1024 * 1024)) * 10) / 10;
    const cpu_cores = cpus.length || 1;
    const cpu_model = cpus.length > 0 ? cpus[0].model : 'Generic CPU';
    const platform = os.platform();
    const arch = os.arch();

    // Display check: HEADLESS or DISPLAY env flag
    const has_display = process.env.DISPLAY !== '' && process.env.HEADLESS !== 'true';

    const gpu = detectGpu();

    return {
      platform,
      arch,
      cpu_cores,
      cpu_model,
      memory_total_gb,
      gpu,
      has_display
    };
  } catch (err) {
    return {
      platform: os.platform(),
      arch: os.arch(),
      cpu_cores: 1,
      cpu_model: 'Unknown',
      memory_total_gb: 2,
      gpu: { present: false, name: null },
      has_display: true
    };
  }
}

function suggestProfile(report) {
  if (!report || report.has_display === false) {
    return 'server_headless';
  }

  const memory = report.memory_total_gb || 0;
  const cores = report.cpu_cores || 1;

  if (memory >= 8 && cores >= 4) {
    return 'full_swarm';
  }

  if (memory < 4) {
    return 'server_headless';
  }

  return 'developer';
}

module.exports = {
  getHardwareReport,
  suggestProfile
};
