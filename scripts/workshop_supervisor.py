"""Run from Laptop 2's existing sandboxed timer; original worker is retained."""
import fcntl
import json
import sqlite3
import sys
from pathlib import Path
import requests

ROOT = Path.home() / '.ai-coder'
sys.path.insert(0, str(ROOT / 'kingdom-automation-source'))
sys.path.insert(0, str(ROOT / 'app'))
from backend.runtime.automation import AutomationSupervisor
from backend.runtime.workshop_adapter import WorkshopAdapter
import skill_workshop


def main():
    state = ROOT / 'skill-workshop/automation.sqlite3'
    with (ROOT / 'skill-workshop/supervisor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        session = requests.Session()
        session.headers['Authorization'] = 'Bearer ' + (ROOT / 'kingdom-automation-data/data/owner-token').read_text().strip()
        def policy():
            response = session.get('http://127.0.0.1:8013/runtime/policy', timeout=10)
            response.raise_for_status()
            return response.json()['level']
        def event(kind, payload):
            # Bounded, secret-free local operational journal; state is also visible
            # through the authenticated Kingdom inventory API.
            journal = ROOT / 'skill-workshop/supervisor-events.jsonl'
            if journal.exists() and journal.stat().st_size > 262144:
                journal.write_text('\n'.join(journal.read_text().splitlines()[-100:]) + '\n')
            with journal.open('a') as log:
                log.write(json.dumps({'type': kind, 'data': payload}) + '\n')
            try:
                session.post('http://127.0.0.1:8013/automations/laptop2-skill-workshop/report', timeout=10).raise_for_status()
            except requests.RequestException:
                pass  # Durable local state remains the source of truth.
        supervisor = AutomationSupervisor(lambda: sqlite3.connect(state, timeout=15), policy, event)
        adapter = WorkshopAdapter(ROOT, lambda: skill_workshop.tick(ROOT))
        supervisor.register(adapter)
        with sqlite3.connect(state) as db:
            current = supervisor._load(db, adapter.id)
        if current['lease']:
            # Exclusive flock proves the previous supervisor process has stopped.
            supervisor.recover_stopped(adapter.id, current['lease'])
        try:
            policy()
        except requests.RequestException:
            if current['owner'] == 'original':
                # A not-yet-adopted timer remains independent of the candidate.
                adapter.run_original()
                return
            raise  # After adoption, unknown autonomy must fail closed.
        supervisor.run(adapter.id)


if __name__ == '__main__':
    main()
