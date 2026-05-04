import requests
import time
import platform

def run():
    commander = input("Commander URL: ")

    name = platform.node()

    while True:
        try:
            task = requests.get(f"{commander}/task").json()

            if task:
                result = {
                    "knight": name,
                    "output": f"processed {task}"
                }

                requests.post(f"{commander}/result", json=result)

        except:
            pass

        time.sleep(2)

run()
