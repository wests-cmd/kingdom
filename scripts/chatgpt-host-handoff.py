"""Run by an authorized operator, never registered as a Kingdom model tool.

Secret export requires non-terminal stdout. Use existing pinned private SSH,
not chat, argv, logs, a public HTTP endpoint, or an unprotected temporary file.
"""
import argparse
import json
from pathlib import Path
import sys
import sqlite3
from contextlib import contextmanager

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.models.chatgpt_plan import ChatGPTPlanConnection, ChatGPTPlanError
from backend.models.chatgpt_handoff import ChatGPTHostHandoff, MAX_BUNDLE, bundle_digest


class ExistingStore:
    """Use only the selected existing DB; never initialize a default app DB."""
    def __init__(self, path):
        self.db_path = path

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            with conn:
                yield conn
        finally:
            conn.close()


def read_record(stream):
    if stream.isatty():
        raise ChatGPTPlanError('handoff_private_stdin_required')
    raw = stream.read(MAX_BUNDLE+1)
    if len(raw) > MAX_BUNDLE:
        raise ChatGPTPlanError('handoff_invalid')
    try:
        return json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise ChatGPTPlanError('handoff_invalid') from error


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--secrets', required=True, type=Path)
    phases = parser.add_subparsers(dest='phase', required=True)
    prepare = phases.add_parser('prepare')
    prepare.add_argument('--target-host-id', required=True)
    prepare.add_argument('--secret-stdout', action='store_true', required=True)
    resume = phases.add_parser('export-existing')
    resume.add_argument('--transfer-id', required=True)
    resume.add_argument('--secret-stdout', action='store_true', required=True)
    receive = phases.add_parser('import')
    receive.add_argument('--expected-sha256', required=True)
    phases.add_parser('complete')
    phases.add_parser('activate')
    status = phases.add_parser('status')
    status.add_argument('--transfer-id', required=True)
    args = parser.parse_args(argv)
    try:
        if not args.database.is_absolute() or not args.secrets.is_absolute():
            raise ChatGPTPlanError('handoff_absolute_paths_required')
        # Refuse unsafe export before constructing/changing any database state.
        if args.phase in ('prepare','export-existing') and sys.stdout.isatty():
            raise ChatGPTPlanError('handoff_private_stdout_required')
        if not args.database.is_file() or args.database.is_symlink():
            raise ChatGPTPlanError('handoff_existing_store_required')
        if any(p.is_symlink() for p in (args.database, *args.database.parents, args.secrets, *args.secrets.parents)):
            raise ChatGPTPlanError('handoff_existing_store_required')
        connection = ChatGPTPlanConnection(ExistingStore(args.database), root=args.secrets)
        handoff = ChatGPTHostHandoff(connection)
        if args.phase == 'prepare':
            result = handoff.prepare(target_host_id=args.target_host_id)
        elif args.phase == 'export-existing':
            result = handoff.export_existing(args.transfer_id)
        elif args.phase == 'import':
            result = handoff.import_bundle(read_record(sys.stdin), expected_sha256=args.expected_sha256)
        elif args.phase == 'complete':
            result = handoff.complete(read_record(sys.stdin))
        elif args.phase == 'activate':
            result = handoff.activate(read_record(sys.stdin))
        else:
            result = handoff.status(args.transfer_id)
        if args.phase in ('prepare','export-existing'):
            print(json.dumps({'transfer_id':result['transfer_id'],'bundle_sha256':bundle_digest(result)}, sort_keys=True), file=sys.stderr)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (ChatGPTPlanError, OSError, sqlite3.Error) as error:
        code = error.code if isinstance(error, ChatGPTPlanError) else 'handoff_io_outcome_unknown'
        print(json.dumps({'error':code,'scope':'No automatic rollback or retry; inspect the retained handoff before continuing.'}), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
