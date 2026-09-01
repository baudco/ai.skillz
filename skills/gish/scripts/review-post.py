#!/usr/bin/env python3

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


DIGEST = re.compile(r'^[0-9a-f]{64}$')
REPOSITORY = re.compile(
    r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$'
)


@dataclass(frozen=True)
class ReviewTarget:
    backend: str
    repository: str
    pr: int
    head: str
    event: str
    actor: str


def git_worktree() -> Path:
    result = subprocess.run(
        ['git', 'rev-parse', '--show-toplevel'],
        check=True,
        capture_output=True,
        text=True,
    )
    return Path(result.stdout.strip()).resolve()


def validate_body(
    value: str,
    worktree: Path,
    expected_digest: str,
) -> tuple[Path, bytes]:
    if not DIGEST.fullmatch(expected_digest):
        raise ValueError(
            'SHA-256 digest is not lowercase hexadecimal'
        )

    requested = Path(value).expanduser()
    if requested.is_symlink():
        raise ValueError('review body must not be a symlink')
    path = requested.resolve(strict=True)
    root = worktree.resolve(strict=True)
    if not path.is_relative_to(root):
        raise ValueError(
            'review body is outside the active worktree'
        )
    if not path.is_file():
        raise ValueError('review body is not a regular file')

    payload = path.read_bytes()
    if not payload:
        raise ValueError('review body is empty')
    if b'\x00' in payload:
        raise ValueError('review body contains a NUL byte')
    try:
        payload.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError(
            'review body is not valid UTF-8'
        ) from error

    actual_digest = hashlib.sha256(payload).hexdigest()
    if actual_digest != expected_digest:
        raise ValueError('review body SHA-256 digest changed')
    return path, payload


def validate_target(target: ReviewTarget) -> None:
    if target.backend != 'gh':
        raise ValueError(
            f'unsupported review backend: {target.backend}'
        )
    if not REPOSITORY.fullmatch(target.repository):
        raise ValueError('repository must use owner/name form')
    if target.pr <= 0:
        raise ValueError('PR number must be positive')
    if not target.head:
        raise ValueError('reviewed head commit is empty')
    if target.event != 'comment':
        raise ValueError(
            'only the comment review event is supported'
        )
    if not target.actor:
        raise ValueError('publishing account is empty')


def parse_json(payload: str, operation: str) -> dict[str, Any]:
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise ValueError(f'{operation} response is not an object')
    return value


def publish_github(
    target: ReviewTarget,
    body_file: Path,
    gh: str,
) -> dict[str, Any]:
    token = subprocess.run(
        [gh, 'auth', 'token'],
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    if not token:
        raise ValueError('GitHub authentication token is empty')
    environment = os.environ.copy()
    environment['GH_TOKEN'] = token

    account = subprocess.run(
        [gh, 'api', 'user', '--jq', '.login'],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    if account.stdout.strip() != target.actor:
        raise ValueError(
            'authenticated GitHub account does not match approval'
        )

    view = subprocess.run(
        [
            gh,
            'pr',
            'view',
            str(target.pr),
            '--repo',
            target.repository,
            '--json',
            'headRefOid,state,url',
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    info = parse_json(view.stdout, 'PR metadata')
    if info.get('state') != 'OPEN':
        raise ValueError('target PR is not open')
    if info.get('headRefOid') != target.head:
        raise ValueError('target PR head moved after review')

    endpoint = (
        f'repos/{target.repository}/pulls/'
        f'{target.pr}/reviews'
    )
    result = subprocess.run(
        [
            gh,
            'api',
            endpoint,
            '--method',
            'POST',
            '--raw-field',
            'event=COMMENT',
            '--raw-field',
            f'commit_id={target.head}',
            '--field',
            f'body=@{body_file}',
        ],
        check=True,
        capture_output=True,
        env=environment,
        text=True,
    )
    return parse_json(result.stdout, 'review publication')


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        description=(
            'Publish one approved top-level review through gish.'
        ),
    )
    result.add_argument('--backend', required=True)
    result.add_argument('--repo', required=True)
    result.add_argument('--pr', required=True, type=int)
    result.add_argument('--body-file', required=True)
    result.add_argument('--sha256', required=True)
    result.add_argument('--head', required=True)
    result.add_argument('--event', required=True)
    result.add_argument('--actor', required=True)
    result.add_argument('--worktree')
    result.add_argument('--gh', default='gh')
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    target = ReviewTarget(
        backend=args.backend,
        repository=args.repo,
        pr=args.pr,
        head=args.head,
        event=args.event,
        actor=args.actor,
    )
    try:
        validate_target(target)
        worktree = (
            Path(args.worktree).resolve()
            if args.worktree
            else git_worktree()
        )
        source_file, payload = validate_body(
            args.body_file,
            worktree,
            args.sha256,
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            body_file = Path(temp_dir) / 'review.md'
            body_file.write_bytes(payload)
            body_file.chmod(0o600)
            result = publish_github(
                target,
                body_file,
                args.gh,
            )
    except (
        json.JSONDecodeError,
        OSError,
        subprocess.CalledProcessError,
        ValueError,
    ) as error:
        print(
            f'Review publication refused: {error}',
            file=sys.stderr,
        )
        return 1

    review_id = result.get('id', 'unknown')
    review_url = result.get('html_url')
    if not review_url:
        links = result.get('_links')
        if isinstance(links, dict):
            html = links.get('html')
            if isinstance(html, dict):
                review_url = html.get('href')
    print(f'Published review {review_id}')
    if review_url:
        print(f'URL: {review_url}')
    print(f'Body: {source_file}')
    print(f'SHA-256: {args.sha256}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
