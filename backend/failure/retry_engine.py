import time

class RetryEngine:

    def retry(self, fn, attempts=3):

        for _ in range(attempts):

            try:
                return fn()

            except Exception:
                time.sleep(1)

        raise Exception("Retry failed")
