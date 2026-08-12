#!/usr/bin/env python3

import argparse
import hashlib
import re
import textwrap
from pathlib import Path


FOOTER = re.compile(
    r'\s*\(this\s+review\s+was\s+generated\s+in\s+some\s+part\s+by\s+'
    r'`[^`]+`\s+using\s+`[^`]+`\s+\(`[^`]+`\)\)\s*'
)


def disclosure(
    harness: str,
    model: str,
    provider: str,
) -> str:
    '''
    Render the code-review disclosure paragraph.

    '''
    value = (
        f'(this review was generated in some part by '
        f'`{harness}` using `{model}` (`{provider}`))'
    )
    return textwrap.fill(
        value,
        width=79,
        break_long_words=False,
        break_on_hyphens=False,
    )


def finalize(
    body: str,
    harness: str,
    model: str,
    provider: str,
) -> str:
    '''
    Replace any prior footer and append exactly one disclosure.

    '''
    content = FOOTER.sub('', body).rstrip()
    if not content:
        raise ValueError('review body is empty')
    footer = disclosure(harness, model, provider)
    return f'{content}\n\n{footer}\n'


def parser() -> argparse.ArgumentParser:
    '''
    Build the command-line parser.

    '''
    result = argparse.ArgumentParser()
    result.add_argument('--body-file', required=True)
    result.add_argument('--harness', required=True)
    result.add_argument('--model', required=True)
    result.add_argument('--provider', required=True)
    return result


def main(argv: list[str] | None = None) -> int:
    '''
    Finalize one body file and print its byte digest.

    '''
    args = parser().parse_args(argv)
    path = Path(args.body_file)
    if path.is_symlink() or not path.is_file():
        raise ValueError('review body must be a regular file')
    body = path.read_text(encoding='utf-8')
    result = finalize(
        body,
        args.harness,
        args.model,
        args.provider,
    )
    path.write_text(result, encoding='utf-8')
    digest = hashlib.sha256(result.encode()).hexdigest()
    print(digest)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
