#!/usr/bin/env python3

import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


FORK_TITLE = re.compile(
    r'^(?P<base>.+) \(fork #(?P<number>[1-9][0-9]*)\)$'
)
DAY_MS = 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class Session:
    id: str
    title: str
    directory: str
    updated: int


@dataclass(frozen=True)
class Selection:
    directory: str
    older_than_days: float
    protected: Session | None
    candidates: tuple[Session, ...]


def resolved_directory(value: str) -> str:
    return str(Path(value).expanduser().resolve())


def valid_age(value: float) -> bool:
    return math.isfinite(value) and value >= 0


def parse_session(value: Any) -> Session:
    if not isinstance(value, dict):
        raise ValueError('session entry is not an object')

    required = ('id', 'title', 'directory', 'updated')
    missing = [key for key in required if key not in value]
    if missing:
        names = ', '.join(missing)
        raise ValueError(f'session entry is missing: {names}')

    session_id = value['id']
    title = value['title']
    directory = value['directory']
    updated = value['updated']
    if not all(
        isinstance(item, str)
        for item in (session_id, title, directory)
    ):
        raise ValueError(
            'session id, title, or directory is not text'
        )
    if not session_id or not directory:
        raise ValueError('session id or directory is empty')
    if not isinstance(updated, int) or isinstance(updated, bool):
        raise ValueError(
            'session updated timestamp is not an integer'
        )
    if updated < 0:
        raise ValueError('session updated timestamp is negative')

    return Session(
        id=session_id,
        title=title,
        directory=resolved_directory(directory),
        updated=updated,
    )


def parse_sessions(payload: str) -> tuple[Session, ...]:
    value = json.loads(payload)
    if not isinstance(value, list):
        raise ValueError('OpenCode session JSON is not a list')
    sessions = tuple(parse_session(item) for item in value)
    ids = [session.id for session in sessions]
    if len(ids) != len(set(ids)):
        raise ValueError('OpenCode session JSON has duplicate ids')
    return sessions


def list_sessions(opencode: str) -> tuple[Session, ...]:
    command = [
        opencode,
        'session',
        'list',
        '--pure',
        '--format',
        'json',
    ]
    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return parse_sessions(result.stdout)


def select_sessions(
    sessions: Sequence[Session],
    directory: str,
    older_than_days: float,
    now_ms: int,
) -> Selection:
    selected_directory = resolved_directory(directory)
    local = tuple(
        session
        for session in sessions
        if session.directory == selected_directory
    )
    protected = max(
        local,
        key=lambda item: item.updated,
        default=None,
    )
    cutoff = now_ms - int(older_than_days * DAY_MS)
    candidates = tuple(
        sorted(
            (
                session
                for session in local
                if session != protected
                and session.updated <= cutoff
                and FORK_TITLE.fullmatch(session.title)
            ),
            key=lambda item: (item.updated, item.id),
        )
    )
    return Selection(
        directory=selected_directory,
        older_than_days=older_than_days,
        protected=protected,
        candidates=candidates,
    )


def selection_token(selection: Selection) -> str:
    value = {
        'version': 1,
        'directory': selection.directory,
        'older_than_days': selection.older_than_days,
        'protected': (
            None
            if selection.protected is None
            else {
                'id': selection.protected.id,
                'title': selection.protected.title,
            }
        ),
        'candidates': [
            {
                'id': session.id,
                'title': session.title,
                'updated': session.updated,
            }
            for session in selection.candidates
        ],
    }
    payload = json.dumps(
        value,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True,
    ).encode()
    return hashlib.sha256(payload).hexdigest()


def display_time(value: int) -> str:
    stamp = datetime.fromtimestamp(
        value / 1000,
        tz=timezone.utc,
    )
    return stamp.isoformat(timespec='seconds')


def print_preview(
    selection: Selection,
    token: str,
    now_ms: int,
) -> None:
    print(f'Directory: {selection.directory}')
    print(f'Older than: {selection.older_than_days:g} days')
    if selection.protected is None:
        print('Protected newest session: none')
    else:
        protected = selection.protected
        print(
            'Protected newest session: '
            f'{protected.id}  {protected.title!r}'
        )

    print(f'Candidates: {len(selection.candidates)}')
    for session in selection.candidates:
        age = (now_ms - session.updated) / DAY_MS
        updated = display_time(session.updated)
        print(
            f'  {session.id}  age={age:.1f}d  '
            f'updated={updated}  {session.title!r}'
        )
    if selection.candidates:
        print(f'Selection token: {token}')


def delete_sessions(
    selection: Selection,
    opencode: str,
) -> int:
    deleted: list[Session] = []
    for session in selection.candidates:
        command = [
            opencode,
            'session',
            'delete',
            session.id,
            '--pure',
        ]
        try:
            subprocess.run(command, check=True)
        except subprocess.CalledProcessError as error:
            print(
                f'Deletion failed for {session.id}: {error}',
                file=sys.stderr,
            )
            if deleted:
                deleted_ids = ', '.join(
                    item.id for item in deleted
                )
                print(
                    f'Already deleted: {deleted_ids}',
                    file=sys.stderr,
                )
            print(
                'Run a fresh preview before retrying.',
                file=sys.stderr,
            )
            return 1
        deleted.append(session)

    for session in deleted:
        print(f'Deleted {session.id}  {session.title!r}')
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            'Safely clean stale OpenCode fork sessions.'
        ),
    )
    result.add_argument('--directory', default=str(Path.cwd()))
    result.add_argument(
        '--older-than-days',
        type=float,
        default=7.0,
    )
    result.add_argument('--opencode', default='opencode')
    result.add_argument('--apply', metavar='TOKEN')
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if not valid_age(args.older_than_days):
        print(
            '--older-than-days must be finite and non-negative',
            file=sys.stderr,
        )
        return 2

    try:
        sessions = list_sessions(args.opencode)
        now_ms = time.time_ns() // 1_000_000
        selection = select_sessions(
            sessions=sessions,
            directory=args.directory,
            older_than_days=args.older_than_days,
            now_ms=now_ms,
        )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(
            f'Unable to list sessions: {error}',
            file=sys.stderr,
        )
        return 1

    token = selection_token(selection)
    print_preview(selection, token, now_ms)
    if not selection.candidates:
        return 0
    if args.apply is None:
        print(
            'No sessions deleted. Obtain explicit approval first.'
        )
        return 0
    if args.apply != token:
        print(
            'Selection changed or token is invalid; '
            'no sessions deleted.',
            file=sys.stderr,
        )
        return 2
    return delete_sessions(selection, args.opencode)


if __name__ == '__main__':
    raise SystemExit(main())
