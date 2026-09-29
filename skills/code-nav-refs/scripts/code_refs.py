'''
Validate editor-jumpable locations in an assistant's Markdown reply.

'''
import argparse
import hashlib
from pathlib import Path
import re
import subprocess
import sys


_PATH = (
    r'(?:/|\./|\.\./)?'
    r'(?:[\w.-]+/)*[\w.-]+\.[\w]+'
)
_REF = re.compile(
    rf'(?P<path>{_PATH}):(?P<first>~?\d+)'
    rf'(?:-(?P<last>~?\d+))?'
    rf'(?::(?P<column>\d+))?'
)
_LINK_REF = re.compile(
    r'(?P<path>/[^<>\n]+):(?P<first>~?\d+)'
    r'(?:-(?P<last>~?\d+))?'
    r'(?::(?P<column>\d+))?'
)
_WEB_LINE = re.compile(rf'{_PATH}#L\d+')
_SPANS = re.compile(r'(?<!`)`([^`\n]+)`(?!`)')
_LINKS = re.compile(r'\[[^\]]+\]\(([^)]+)\)')
_FENCE = re.compile(r'^ {0,3}(?P<mark>`{3,}|~{3,})')
_URL = re.compile(r'https?://\S+')


def git_root(directory: Path) -> Path|None:
    '''
    Resolve the reply root independently of any editing worktree.

    '''
    result = subprocess.run(
        ['git', '-C', str(directory), 'rev-parse',
         '--show-toplevel'],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        return None
    return Path(result.stdout.strip()).resolve()


def _check_location(
    token: str,
    reply_root: Path|None,
    absolute_only: bool,
) -> str|None:
    '''
    Verify the location's file, worktree and inclusive line range.

    '''
    ref = _REF.fullmatch(token) or _LINK_REF.fullmatch(token)
    if ref is None:
        return 'not a single path:line location'
    raw = Path(ref['path'])
    if not raw.is_absolute() and absolute_only:
        return 'use an absolute path for this reply'
    if not raw.is_absolute() and reply_root is None:
        return 'no verified reply root for a relative path'
    try:
        path = (raw if raw.is_absolute() else reply_root / raw)
        path = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return 'file does not exist'
    if not raw.is_absolute() and not path.is_relative_to(
        reply_root
    ):
        return 'relative path escapes the reply worktree'
    if not path.is_file():
        return 'target is not a regular file'

    first = ref['first']
    last = ref['last'] or first
    if '~' in first or '~' in last:
        return 'line numbers must be exact'
    start = int(first)
    stop = int(last)
    if stop < start:
        return 'line range is reversed'
    try:
        count = 0
        cited_line = b''
        with path.open('rb') as source:
            for count, content in enumerate(source, 1):
                if count == start:
                    cited_line = content.rstrip(b'\r\n')
    except OSError:
        return 'file cannot be read'
    if stop > count:
        return f'line {stop} exceeds file length {count}'
    column = ref['column']
    if column and int(column) > len(
        cited_line.decode('utf-8', errors='replace')
    ) + 1:
        return f'column {column} exceeds line {start}'
    return None


def validate_response(
    text: str,
    reply_root: Path|None,
    *,
    absolute_only: bool = False,
    plan_commands: str|None = None,
    plan_overview: str|None = None,
) -> list[str]:
    '''
    Check prose citations while excluding runnable fenced blocks.

    A fenced command may contain colon syntax without citing a
    source location. Inline prose paths must use one complete
    backticked path:line reference or a local-file Markdown link.

    '''
    problems: list[str] = []
    fence: str|None = None
    for number, line in enumerate(text.splitlines(), 1):
        opening = _FENCE.match(line)
        if opening:
            mark = opening['mark']
            if fence is None:
                fence = mark
            elif mark[0] == fence[0] and len(mark) >= len(fence):
                fence = None
            continue
        if fence is not None:
            continue

        prose = line
        for link in _LINKS.finditer(line):
            raw = link[1]
            if raw.startswith('<') and '>' in raw:
                target = raw[1:raw.index('>')]
            else:
                target = raw.split(' "', 1)[0]
            if not _URL.fullmatch(target):
                if (
                    _REF.fullmatch(target)
                    or _LINK_REF.fullmatch(target)
                ):
                    issue = _check_location(
                        target, reply_root, absolute_only,
                    )
                    if issue:
                        problems.append(
                            f'line {number}: {target}: {issue}'
                        )
                elif _REF.search(target) or _WEB_LINE.search(target):
                    problems.append(
                        f'line {number}: {target}: invalid file link'
                    )
            prose = prose.replace(link[0], ' ', 1)

        for span in _SPANS.finditer(prose):
            token = span[1]
            if '://' in token:
                pass
            elif _REF.fullmatch(token):
                issue = _check_location(
                    token, reply_root, absolute_only,
                )
                if issue:
                    problems.append(
                        f'line {number}: {token}: {issue}'
                    )
            elif _REF.search(token) and not any(
                char.isspace() for char in token
            ):
                problems.append(
                    f'line {number}: {token}: '
                    'wrap one complete location per code span'
                )
            elif _WEB_LINE.search(token) and '://' not in token:
                problems.append(
                    f'line {number}: {token}: use path:line, '
                    'not #L line fragments'
                )
            prose = prose.replace(span[0], ' ', 1)

        prose = _URL.sub(' ', prose)
        for ref in _REF.finditer(prose):
            problems.append(
                f'line {number}: {ref[0]}: '
                'wrap the complete location in backticks'
            )
        for ref in _WEB_LINE.finditer(prose):
            problems.append(
                f'line {number}: {ref[0]}: use path:line, '
                'not #L line fragments'
            )
    if plan_commands is not None:
        commands = plan_commands.strip('\n')
        fence = re.compile(
            r'^```(?:xonsh|xsh|bash)\n(.*?)\n```$',
            re.MULTILINE | re.DOTALL,
        )
        if not any(
            match[1].strip('\n') == commands
            for match in fence.finditer(text)
        ):
            problems.append(
                'complete pinned plan command block is missing '
                'or differs from the rendered artifact'
            )
    if plan_overview is not None and (
        plan_overview.strip() not in text
    ):
        problems.append(
            'complete pinned plan overview is missing '
            'or differs from the rendered artifact'
        )
    return problems


def main(argv: list[str]|None = None) -> int:
    '''
    Validate one reply read from standard input.

    '''
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reply-root', type=Path, required=True)
    parser.add_argument('--absolute-only', action='store_true')
    parser.add_argument('--plan-commands', type=Path)
    parser.add_argument('--plan-overview', type=Path)
    parser.add_argument('--plan-commands-sha256')
    parser.add_argument('--plan-overview-sha256')
    args = parser.parse_args(argv)
    root = git_root(args.reply_root)
    if root is None and not args.absolute_only:
        parser.error('reply root is not a Git worktree')
    for label in ('plan_commands', 'plan_overview'):
        source = getattr(args, label)
        expected = getattr(args, f'{label}_sha256')
        if (source is None) != (expected is None):
            parser.error(
                f'--{label.replace("_", "-")} requires its '
                '--sha256 counterpart'
            )
        if source is not None:
            if not re.fullmatch(r'[0-9a-f]{64}', expected):
                parser.error(f'invalid {label} sha256')
            observed = hashlib.sha256(
                source.read_bytes()
            ).hexdigest()
            if observed != expected:
                parser.error(f'{label} artifact digest changed')
    problems = validate_response(
        sys.stdin.read(), root,
        absolute_only=args.absolute_only,
        plan_commands=(
            args.plan_commands.read_text()
            if args.plan_commands else None
        ),
        plan_overview=(
            args.plan_overview.read_text()
            if args.plan_overview else None
        ),
    )
    for problem in problems:
        print(problem, file=sys.stderr)
    return bool(problems)


if __name__ == '__main__':
    sys.exit(main())
