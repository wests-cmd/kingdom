"""Submit a signed worker enrollment; never approve it or start another daemon."""
import argparse
import getpass
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.cluster.knight_daemon import KnightDaemon


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capabilities', nargs='+', required=True)
    args = parser.parse_args()
    node_id = os.environ.get('NODE_ID')
    commander_url = os.environ.get('COMMANDER_URL')
    if not node_id or not commander_url:
        parser.error('Run inside a configured Compose worker with NODE_ID and COMMANDER_URL.')
    if not sys.stdin.isatty():
        parser.error('An interactive terminal is required to enter the private pairing code.')
    code = getpass.getpass('Single-use Add Knight pairing code (hidden): ').strip()
    if not code:
        parser.error('Pairing code cannot be empty.')
    daemon = KnightDaemon(node_id, os.environ.get('DISPLAY_NAME', node_id),
                          commander_url, 8001, args.capabilities, 'data')
    if not daemon.request_pairing(code):
        raise SystemExit('Enrollment failed. Check the commander and create a fresh invitation.')
    print('Signed enrollment submitted. Review the fingerprint and explicitly approve this worker in Nodes & Cluster.')
    print('No permissions were granted by this command. The existing daemon will observe owner approval.')


if __name__ == '__main__':
    main()
