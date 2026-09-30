#!/bin/bash
set -euo pipefail
# Native installations are upgraded with their verified platform installer.
# Discovery never changes the installed application or claims an update succeeded.
python3 - <<'PY'
import json
from backend.system.updater import check_updates
print(json.dumps(check_updates(), indent=2))
PY
