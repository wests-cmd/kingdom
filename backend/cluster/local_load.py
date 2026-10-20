"""Measured local load for signed peer reports; unavailable never means idle."""
import math


def _power_metrics(psutil):
    unknown = {'status': 'unknown', 'battery_percent': None, 'plugged': None}
    try:
        battery = psutil.sensors_battery()
        if battery is None:
            return {'status': 'no_battery', 'battery_percent': None, 'plugged': None}
        percent, plugged = battery.percent, battery.power_plugged
        if (type(percent) not in (int, float) or not math.isfinite(percent)
                or not 0 <= percent <= 100 or type(plugged) is not bool):
            return unknown
        return {'status': 'battery', 'battery_percent': percent, 'plugged': plugged}
    except (AttributeError, OSError, RuntimeError, NotImplementedError):
        return unknown


def local_load_metrics():
    try:
        import psutil
        # A bounded interval measures CPU use instead of the first-call zero
        # returned by psutil's nonblocking sampler on a new request thread.
        measured = {'cpu_percent': psutil.cpu_percent(interval=0.1),
                    'memory_percent': psutil.virtual_memory().percent}
        if any(type(value) not in (int, float) or not math.isfinite(value)
               or not 0 <= value <= 100 for value in measured.values()):
            return {}
        measured['power'] = _power_metrics(psutil)
        return measured
    except (ImportError, OSError, RuntimeError):
        return {}
