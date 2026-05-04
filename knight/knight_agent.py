import socket
import requests
from modules.ilmfit import ILMFit
import platform
import requests

def get_commander_ip():
    print("Knight setup: please enter Commander IP or hostname.")
    return input("Commander IP: ").strip()

def main():
    commander_ip = get_commander_ip()
    url = f"http://{commander_ip}:8000/register"

    ilm = ILMFit()
    caps = ilm.capabilities()

    payload = {
        "name": socket.gethostname(),
        "capabilities": caps
        # "requested_level": 2  # uncomment to request a specific level
    }
def main():
    url = input("Commander URL: ")
    payload = {"name": platform.node()}
    requests.post(f"{url}/register", json=payload)

    print(f"[INFO] Registering with Commander at {url}")
    r = requests.post(url, json=payload, timeout=10)
    print("[INFO] Commander response:", r.json())

if __name__ == "__main__":
    main()
