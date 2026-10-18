"""Measured local load for signed peer reports; unavailable never means idle."""
import math


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
        return measured
    except (ImportError, OSError, RuntimeError):
        return {}
