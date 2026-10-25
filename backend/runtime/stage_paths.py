"""Plan-selected file targets, separate from model-generated argument data."""
from pathlib import PurePosixPath, PureWindowsPath


def validate_paths(paths, sequence, protocol):
    if paths is None:
        return []
    if not isinstance(paths, list):
        raise ValueError('Stage paths must be a list')
    if not paths:
        return []
    if protocol != 'structured' or len(paths) != len(sequence):
        raise ValueError('Bound paths require matching structured file stages')
    for tool, path in zip(sequence, paths):
        if tool not in {'workspace_read', 'workspace_write', 'workspace_list'}:
            raise ValueError('Only file stages support bound paths')
        if (not isinstance(path, str) or not 1 <= len(path) <= 300
                or '\\' in path or ':' in path or '\x00' in path
                or PurePosixPath(path).is_absolute() or PureWindowsPath(path).drive
                or '..' in PurePosixPath(path).parts):
            raise ValueError('Stage paths must stay relative to the workspace')
    return list(paths)


def bind_arguments(arguments, path):
    if not isinstance(arguments, dict) or 'path' in arguments:
        raise ValueError('The model cannot replace a plan-selected path')
    return {**arguments, 'path': path}
