#!/usr/bin/env python3
"""Rewrap markdown prose to fill-width line limit.

Reads markdown from stdin (or file arg), rewraps prose
paragraphs and bullet text to the target column width
using greedy (textwrap) fill. Preserves structure:
headers, bullets, sub-bullets, HTML comments, code
blocks, link refs, blank lines, credit footers.

Measures **rendered** width for reference-link syntax:
``[display text][ref-id]`` counts only ``display text``
toward the column limit — the ``[ref-id]`` bracket
portion is invisible when rendered.

Usage:
    python rewrap.py < pr_body.md
    python rewrap.py pr_body.md
    python rewrap.py --width 67 < commit_msg.md

Default width: 69 (matching /pr-msg display-col rule).
"""
import argparse
import re
import sys
import textwrap

# Reference-style link: [display text][ref-id]
# Also handles empty-ref shorthand: [display text][]
REF_LINK_RE = re.compile(r'\[([^\]]+)\]\[([^\]]*)\]')


def rendered_len(line: str) -> int:
    '''Return display width of *line*, discounting
    invisible reference-link ``[ref-id]`` portions.

    ``[display][ref]`` → counts only ``display``;
    the surrounding brackets and ref-id vanish in
    rendered markdown.
    '''
    return len(REF_LINK_RE.sub(r'\1', line))


def _rejoin_short_lines(wrapped: str, width: int) -> str:
    '''Post-wrap pass: rejoin lines that were broken
    too aggressively due to reference-link overhead.

    ``textwrap`` measures raw chars, so lines containing
    ref-links get split sooner than necessary. Walk the
    output and merge adjacent lines whenever the
    *rendered* width of the combined line still fits
    within *width*.
    '''
    if '[' not in wrapped or '][' not in wrapped:
        return wrapped

    lines = wrapped.split('\n')
    if len(lines) <= 1:
        return wrapped

    result = [lines[0]]
    for line in lines[1:]:
        stripped = line.lstrip()
        joined = result[-1] + ' ' + stripped
        if rendered_len(joined) <= width:
            result[-1] = joined
        else:
            result.append(line)

    return '\n'.join(result)


def rewrap(text, width=69, indent='', subsequent_indent=None):
    if subsequent_indent is None:
        subsequent_indent = indent
    wrapped = textwrap.fill(
        text, width=width,
        initial_indent=indent,
        subsequent_indent=subsequent_indent,
        break_on_hyphens=False,
        break_long_words=False,
    )
    return _rejoin_short_lines(wrapped, width)


def process(lines, width=69):
    out = []
    i = 0
    in_comment = False
    in_code = False

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        # Code blocks
        if stripped.startswith('```'):
            in_code = not in_code
            out.append(line)
            i += 1
            continue
        if in_code:
            out.append(line)
            i += 1
            continue

        # HTML comments — pass through entirely
        if '<!--' in line and '-->' not in line:
            in_comment = True
            out.append(line)
            i += 1
            continue
        if in_comment:
            out.append(line)
            if '-->' in line:
                in_comment = False
            i += 1
            continue
        if '<!--' in line and '-->' in line:
            out.append(line)
            i += 1
            continue

        # Blank lines
        if not stripped:
            out.append(line)
            i += 1
            continue

        # Headers, HRs, tables
        if stripped.startswith(('#', '---', '|')):
            out.append(line)
            i += 1
            continue

        # Link reference definitions: [ref-id]: URL
        # Pass through as-is (but NOT inline ref-links
        # like [display][ref] which are prose).
        if re.match(r'^\[([^\]]+)\]:\s', stripped):
            out.append(line)
            i += 1
            continue

        # Orphaned sub-bullets (`* `) not nested under
        # a `- ` parent — e.g. sub-bullets following a
        # prose paragraph like `([hash][hash]) ...`.
        # Collect continuation lines and rewrap with
        # 2-space indent + 4-space continuation.
        if stripped.startswith('* '):
            sub_lines = [line]
            i += 1
            while i < len(lines):
                snxt = lines[i]
                ss = snxt.strip()
                if (
                    snxt.startswith('    ')
                    and ss
                    and not ss.startswith('* ')
                    and not ss.startswith('- ')
                ):
                    sub_lines.append(snxt)
                    i += 1
                else:
                    break
            text = ' '.join(
                l.strip() for l in sub_lines
            )
            out.append(
                rewrap(
                    text, width, '  ',
                    subsequent_indent='    ',
                )
            )
            continue

        # Bullets (with possible sub-bullets)
        if stripped.startswith('- '):
            bullet_lines = [line]
            has_subbullets = False
            i += 1
            while i < len(lines):
                nxt = lines[i]
                ns = nxt.strip()
                if ns.startswith('* '):
                    has_subbullets = True
                    break
                if (
                    nxt.startswith('  ')
                    and ns
                    and not ns.startswith('- ')
                ):
                    bullet_lines.append(nxt)
                    i += 1
                else:
                    break

            if has_subbullets:
                text = ' '.join(
                    l.strip() for l in bullet_lines
                )
                out.append(rewrap(text, width, ''))
                while i < len(lines):
                    nxt = lines[i]
                    ns = nxt.strip()
                    if ns.startswith('* '):
                        sub_lines = [nxt]
                        i += 1
                        while i < len(lines):
                            snxt = lines[i]
                            ss = snxt.strip()
                            if (
                                snxt.startswith('    ')
                                and ss
                                and not ss.startswith('* ')
                                and not ss.startswith('- ')
                            ):
                                sub_lines.append(snxt)
                                i += 1
                            else:
                                break
                        text = ' '.join(
                            l.strip()
                            for l in sub_lines
                        )
                        out.append(
                            rewrap(
                                text, width, '  ',
                                subsequent_indent='    ',
                            )
                        )
                    else:
                        break
            else:
                text = ' '.join(
                    l.strip() for l in bullet_lines
                )
                out.append(rewrap(
                    text, width,
                    subsequent_indent='  ',
                ))
            continue

        # Regular prose paragraph
        para = []
        while i < len(lines):
            l = lines[i]
            s = l.strip()
            if not s:
                break
            if s.startswith((
                '#', '---', '- ', '* ',
                '|', '<!--', '```',
            )):
                break
            # Break on link ref defs, not inline links
            if re.match(r'^\[([^\]]+)\]:\s', s):
                break
            para.append(l)
            i += 1

        if para:
            text = ' '.join(l.strip() for l in para)
            out.append(rewrap(text, width))

    return out


def main():
    parser = argparse.ArgumentParser(
        description='Rewrap markdown prose to fill width',
    )
    parser.add_argument(
        'file', nargs='?',
        help='input file (default: stdin)',
    )
    parser.add_argument(
        '-w', '--width', type=int, default=69,
        help='target line width (default: 69)',
    )
    args = parser.parse_args()

    if args.file:
        with open(args.file) as f:
            text = f.read()
    else:
        text = sys.stdin.read()

    lines = text.rstrip('\n').split('\n')
    result = process(lines, args.width)
    print('\n'.join(result))


if __name__ == '__main__':
    main()
