# Copyright (C) 2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Read Pi session metadata without starting Pi or modifying its logs.

- Ownership: `pi_sessions()` discovers JSONL metadata;
  `_resume.resume_target()` selects IDs and launch directories.
- Boundary: native headers/events have untrusted JSON shapes.
  `pi_sessions()` narrows consumed fields before publishing the
  heterogeneous records expected by `list_dialogs()`.

'''

import json
from pathlib import Path
from typing import BinaryIO


# Match Pi 1.5's bounded search for its first parsed header entry.
_HEADER_SCAN_LIMIT_BYTES: int = 1024 * 1024
# Keep unnamed Pi titles as compact as Claude's prompt fallback.
_PROMPT_NAME_LIMIT_CHARS: int = 120


def _reject_json_constant(value: str) -> None:
    '''
    Reject NaN/Infinity just as Pi's native JSON.parse does.

    '''
    raise ValueError('Non-JSON constant: ' + value)


def _session_header(stream: BinaryIO) -> dict|None:
    '''
    Return Pi's first parsed header candidate from `stream`.

    - Inputs: consume the binary `stream` from its current offset.
    - Selection: skip blank, malformed and JSON-falsy scalar lines,
      matching Pi's native discovery rather than guessing filenames.
    - Output: return the first dictionary candidate; `pi_sessions()`
      checks its type and fields. A truthy scalar ends the search.
    - Bounds: stop at `_HEADER_SCAN_LIMIT_BYTES`, so discovery does
      not offer IDs from preambles Pi itself would skip.

    '''
    scanned: int = 0
    while scanned <= _HEADER_SCAN_LIMIT_BYTES:
        line: bytes = stream.readline(
            _HEADER_SCAN_LIMIT_BYTES - scanned + 1,
        )
        if not line:
            return None

        scanned += len(line)
        if scanned > _HEADER_SCAN_LIMIT_BYTES:
            return None
        try:
            value: object = json.loads(
                line.decode('utf-8', errors='replace'),
                parse_constant=_reject_json_constant,
            )

        except ValueError:
            continue
        if (
            value is None
            or
            value is False
            or
            value == 0
            or
            value == ''
        ):
            continue

        if isinstance(value, dict):
            return value

        return None

    return None


def pi_sessions(
    home: Path,
    cwd: str|None,
    all_sources: bool = False,
    include_archived: bool = False,
    *,
    session_layout: str = 'bucketed',
) -> list[dict]:
    '''
    Read a Pi sessions root with explicit bucketed or flat layout.

    Inputs/selection:
    - `session_layout` selects bucketed or flat files under `home`.
    - Require a supported header, exact native ID and absolute saved
      cwd. Apply `cwd` filtering only after counting duplicate IDs.
    - Keep independently resumable forks. `all_sources` and
      `include_archived` have no Pi equivalents and do not filter.

    Outputs:
    - Prefer the last `session_info` name over first-user text,
      capped by `_PROMPT_NAME_LIMIT_CHARS` for unnamed sessions.
    - Return saved model selection, not live-process evidence.
    - Pin CLI lookup with the contained `session_file` path.

    Failures/caller contracts:
    - Reject unsupported layouts and symlinks escaping `home`.
    - Reject duplicate native IDs before eligibility/cwd filtering;
      neither `list_dialogs()` nor Pi may resolve them by recency.
    - Skip malformed headers and corrupt events independently.

    '''
    if session_layout not in ('bucketed', 'flat'):
        raise ValueError(
            f'Unsupported Pi store layout: {session_layout!r}'
        )

    pattern: str = '*/*.jsonl'
    if session_layout == 'flat':
        pattern = '*.jsonl'

    paths: list[Path] = sorted(home.glob(pattern))
    records: dict[str, dict] = {}
    seen: dict[str, str] = {}
    path: Path
    for path in paths:
        canonical: Path = path.resolve()
        if not canonical.is_relative_to(home):
            path_text: str = str(path)
            home_text: str = str(home)
            raise ValueError(
                f'Pi session escapes store: {path_text!r}; '
                f'store={home_text!r}'
            )

        if not canonical.is_file():
            continue

        stream: BinaryIO
        with canonical.open('rb') as stream:
            header: dict|None = _session_header(stream)
            if header is None:
                continue

            did: object = header.get('id')
            saved: object = header.get('cwd')
            if (
                header.get('type') != 'session'
                or
                not isinstance(did, str)
                or
                not did
            ):
                continue

            # Native exact lookup accepts header IDs before checking
            # our supported version/cwd shape. Count those too: an
            # ineligible duplicate could otherwise win its lookup.
            if did in seen:
                previous: str = seen[did]
                current: str = str(canonical)
                raise ValueError(
                    f'Ambiguous Pi dialog ID {did!r}: '
                    f'{previous!r}, {current!r}'
                )

            seen[did] = str(canonical)
            if (
                type(header.get('version', 1)) is not int
                or
                header.get('version', 1) not in (1, 2, 3)
                or
                not isinstance(saved, str)
                or
                not Path(saved).is_absolute()
            ):
                continue

            name: str = ''
            prompt: str = ''
            provider: str|None = None
            model: str|None = None
            line: bytes
            for line in stream:
                try:
                    event: object = json.loads(
                        line,
                        parse_constant=_reject_json_constant,
                    )

                except (
                    ValueError,
                    UnicodeDecodeError,
                ):
                    continue

                if not isinstance(event, dict):
                    continue

                kind: object = event.get('type')
                if kind == 'session_info':
                    title: object = event.get('name')
                    if isinstance(title, str):
                        name = title

                elif kind == 'model_change':
                    selected_provider: object = event.get('provider')
                    selected_model: object = event.get('modelId')
                    if (
                        isinstance(selected_provider, str)
                        and
                        isinstance(selected_model, str)
                    ):
                        provider = selected_provider
                        model = selected_model

                elif (
                    kind == 'message'
                    and
                    not prompt
                ):
                    message: object = event.get('message')
                    if (
                        not isinstance(message, dict)
                        or
                        message.get('role') != 'user'
                    ):
                        continue

                    content: object = message.get('content')
                    if isinstance(content, str):
                        prompt = content[:_PROMPT_NAME_LIMIT_CHARS]

                    elif isinstance(content, list):
                        block: object
                        for block in content:
                            if (
                                isinstance(block, dict)
                                and
                                block.get('type') == 'text'
                                and
                                isinstance(block.get('text'), str)
                            ):
                                prompt = block['text'][
                                    :_PROMPT_NAME_LIMIT_CHARS
                                ]
                                if prompt:
                                    break
            records[did] = {
                'harness': 'pi',
                'id': did,
                'name': (
                    name
                    or
                    prompt
                    or
                    '(untitled)'
                ),
                'cwd': saved,
                'source': 'pi',
                'updated_at': canonical.stat().st_mtime,
                'provider': provider,
                'model': model,
                'session_file': str(canonical),
            }

    result: list[dict] = []
    record: dict
    for record in records.values():
        if (
            cwd is None
            or
            record['cwd'] == cwd
        ):
            result.append(record)

    return result
