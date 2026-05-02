import psutil

class ILMFit:
    def capabilities(self):
        return {
            "cpu_cores": psutil.cpu_count(),
            "ram_gb": round(psutil.virtual_memory().total / 1e9, 2),
            "disk_gb": round(psutil.disk_usage('/').total / 1e9, 2)
        }
