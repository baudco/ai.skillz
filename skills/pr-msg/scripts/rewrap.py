#!/usr/bin/env python3
"""Rewrap markdown prose to fill-width line limit.

Reads markdown from stdin (or file arg), rewraps prose
paragraphs and bullet text to the target column width
using greedy (textwrap) fill. Preserves structure:
headers, bullets, sub-bullets, HTML comments, code
blocks, link refs, blank lines, credit footers.

Usage:
    python rewrap.py < pr_body.md
    python rewrap.py pr_body.md
    python rewrap.py --width 67 < commit_msg.md

Default width: 69 (matching /pr-msg display-col rule).
"""
import argparse
import sys
import textwrap


def rewrap(text, width=69, indent=''):
    return textwrap.fill(
        text, width=width,
        initial_indent=indent,
        subsequent_indent=indent,
        break_on_hyphens=False,
        break_long_words=False,
    )


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

        # Headers, HRs, link refs, tables, credit footer
        if stripped.startswith((
            '#', '---', '|', '[', '(this',
        )):
            out.append(line)
            i += 1
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
                            rewrap(text, width, '  ')
                        )
                    else:
                        break
            else:
                text = ' '.join(
                    l.strip() for l in bullet_lines
                )
                wrapped = textwrap.fill(
                    text, width=width,
                    subsequent_indent='  ',
                    break_on_hyphens=False,
                    break_long_words=False,
                )
                out.append(wrapped)
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
                '|', '[', '<!--', '```',
            )):
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
