#!/usr/bin/env python3
'''
Generate a commit-message style guide from a repo's
git history.

Analyzes N commits and outputs a complete
`style-guide-reference.md` matching the format used
by the `/commit-msg` skill.

Ported from `~/repos/claude_wks/analyze_commits.py`.

'''
import argparse
import re
import subprocess
import sys
from collections import (
    Counter,
    defaultdict,
)
from datetime import date
from pathlib import Path


# -- git log export -------------------------------------------------

def export_commits(
    repo_path: str,
    count: int = 500,
    author: str | None = None,
) -> str:
    '''
    Run `git log` and return the raw export text.

    '''
    cmd: list[str] = [
        'git', '-C', repo_path, 'log',
        '--pretty=format:'
        'COMMIT:%H%n'
        'AUTHOR:%an%n'
        'DATE:%ad%n'
        'SUBJECT:%s%n'
        'BODY:%b%n'
        '---END---',
        '--date=short',
        f'-n{count}',
    ]
    if author:
        cmd.append(f'--author={author}')

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(
            f'git log failed: {result.stderr.strip()}',
            file=sys.stderr,
        )
        sys.exit(1)

    return result.stdout


def get_repo_name(repo_path: str) -> str:
    '''
    Extract the repo basename from the path or git
    remote.

    '''
    result = subprocess.run(
        [
            'git', '-C', repo_path,
            'remote', 'get-url', 'origin',
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        url = result.stdout.strip()
        # https://github.com/user/repo.git -> repo
        # git@github.com:user/repo.git -> repo
        name = url.rstrip('/').rsplit('/', 1)[-1]
        name = name.rsplit('.git', 1)[0]
        return name

    # fallback to directory name
    return Path(repo_path).resolve().name


def get_date_range(commits: list[dict]) -> str:
    '''
    Extract earliest and latest commit dates.

    '''
    dates = [
        c['date'] for c in commits
        if 'date' in c
    ]
    if not dates:
        return 'unknown'

    # dates are YYYY-MM-DD from --date=short
    earliest = min(dates)
    latest = max(dates)
    return f'{earliest} to {latest}'


# -- parsing --------------------------------------------------------

def parse_commits(text: str) -> list[dict]:
    '''
    Parse commit data from git log export text.

    '''
    commits: list[dict] = []
    current: dict = {}

    for line in text.splitlines():

        if line.startswith('COMMIT:'):
            if current:
                commits.append(current)
            current = {'hash': line[7:]}
        elif line.startswith('AUTHOR:'):
            current['author'] = line[7:]
        elif line.startswith('DATE:'):
            current['date'] = line[5:]
        elif line.startswith('SUBJECT:'):
            current['subject'] = line[8:]
        elif line.startswith('BODY:'):
            current['body'] = []
        elif line == '---END---':
            if current:
                commits.append(current)
                current = {}
        elif 'body' in current:
            current['body'].append(line)

    if current:
        commits.append(current)

    for commit in commits:
        if 'body' in commit:
            commit['body'] = '\n'.join(commit['body'])
        else:
            commit['body'] = ''

    return commits


# -- analysis functions ---------------------------------------------
# (ported from ~/repos/claude_wks/analyze_commits.py)

def analyze_subjects(commits: list[dict]) -> dict:
    '''
    Analyze subject line patterns.

    '''
    subjects = [
        c['subject'] for c in commits
        if 'subject' in c
    ]

    # opening verbs
    verbs: list[str] = []
    for subj in subjects:
        if ': ' in subj and not subj.startswith('Merge'):
            parts = subj.split(': ', 1)
            if len(parts) == 2:
                first_word = (
                    parts[1].split()[0]
                    if parts[1]
                    else ''
                )
            else:
                first_word = (
                    subj.split()[0] if subj else ''
                )
        else:
            first_word = subj.split()[0] if subj else ''
        verbs.append(first_word)

    verb_counts = Counter(verbs).most_common(50)

    # lengths
    lengths = [len(s) for s in subjects]
    avg_len = (
        sum(lengths) / len(lengths) if lengths else 0
    )
    max_len = max(lengths) if lengths else 0

    # backtick usage
    with_backticks = sum(
        1 for s in subjects if '`' in s
    )
    pct_backticks = (
        with_backticks / len(subjects) * 100
        if subjects else 0
    )

    # colon usage
    with_colons = sum(
        1 for s in subjects if ': ' in s
    )
    pct_colons = (
        with_colons / len(subjects) * 100
        if subjects else 0
    )

    # ending punctuation
    with_question = sum(
        1 for s in subjects if s.endswith('?')
    )
    with_exclaim = sum(
        1 for s in subjects if s.endswith('!')
    )
    pct_question = (
        with_question / len(subjects) * 100
        if subjects else 0
    )
    pct_exclaim = (
        with_exclaim / len(subjects) * 100
        if subjects else 0
    )

    return {
        'verb_counts': verb_counts,
        'avg_length': avg_len,
        'max_length': max_len,
        'pct_backticks': pct_backticks,
        'pct_colons': pct_colons,
        'pct_question': pct_question,
        'pct_exclaim': pct_exclaim,
        'total': len(subjects),
    }


def analyze_backticks(commits: list[dict]) -> list:
    '''
    Analyze backticked content across all commits.

    '''
    all_text: list[str] = []
    for c in commits:
        all_text.append(c.get('subject', ''))
        all_text.append(c.get('body', ''))

    backticked: list[str] = []
    for text in all_text:
        matches = re.findall(r'`([^`]+)`', text)
        backticked.extend(matches)

    return Counter(backticked).most_common(100)


def analyze_bodies(commits: list[dict]) -> dict:
    '''
    Analyze commit body structure and content.

    '''
    bodies = [c.get('body', '') for c in commits]

    empty = sum(1 for b in bodies if not b.strip())
    pct_empty = (
        empty / len(bodies) * 100 if bodies else 0
    )

    section_markers = [
        'Deats,',
        'Also,',
        'Other,',
        'Impl details,',
        'Further,',
        'Notes,',
        'TODO,',
        'WIP,',
        'Note:',
        'Todos,',
        'Fixes,',
    ]

    marker_counts: Counter = Counter()
    for body in bodies:
        for marker in section_markers:
            if marker in body:
                marker_counts[marker] += 1

    bullet_dash = sum(
        1 for b in bodies
        if '\n- ' in b or b.startswith('- ')
    )
    bullet_star = sum(
        1 for b in bodies
        if '\n  * ' in b or '\n* ' in b
    )
    pct_bullet_dash = (
        bullet_dash / len(bodies) * 100
        if bodies else 0
    )
    pct_bullet_star = (
        bullet_star / len(bodies) * 100
        if bodies else 0
    )

    return {
        'pct_empty': pct_empty,
        'section_markers': marker_counts.most_common(),
        'pct_bullet_dash': pct_bullet_dash,
        'pct_bullet_star': pct_bullet_star,
    }


def analyze_language(commits: list[dict]) -> dict:
    '''
    Analyze language patterns and abbreviations.

    '''
    bodies = [c.get('body', '') for c in commits]
    all_text = ' '.join(bodies)

    abbrevs: dict[str, int] = {
        'bc': 0, 'OW': 0, 'tf': 0, 'obvi': 0,
        'rn': 0, 'dne': 0, 'fn': 0, 'mod': 0,
        'impl': 0, 'sig': 0, 'var': 0, 'env': 0,
        'osenv': 0, 'iface': 0, 'ep': 0, 'bg': 0,
        'tn': 0, 'ctx': 0, 'msg': 0, 'subproc': 0,
        'deps': 0, 'vs': 0, 'tho': 0, 'w/': 0,
        'wo/': 0, 'gonna': 0, 'wanna': 0,
        'dunno': 0, 'prolly': 0, 'ofc': 0, 'wtf': 0,
    }

    for abbrev in abbrevs:
        pattern = r'\b' + re.escape(abbrev) + r'\b'
        abbrevs[abbrev] = len(
            re.findall(pattern, all_text)
        )

    used_abbrevs = {
        k: v for k, v in abbrevs.items() if v > 0
    }

    tone_patterns: dict[str, int] = {
        'Woops': 0,
        'woops': 0,
        'XD': 0,
        'lol': 0,
        '..': 0,
    }

    for pat in tone_patterns:
        tone_patterns[pat] = all_text.count(pat)

    return {
        'abbreviations': sorted(
            used_abbrevs.items(),
            key=lambda x: x[1],
            reverse=True,
        ),
        'tone_indicators': {
            k: v for k, v in tone_patterns.items()
            if v > 0
        },
    }


def analyze_special_patterns(
    commits: list[dict],
) -> dict:
    '''
    Analyze special commit patterns.

    '''
    subjects = [
        c.get('subject', '') for c in commits
    ]
    bodies = [c.get('body', '') for c in commits]

    wip = sum(
        1 for s in subjects if s.startswith('WIP')
    )
    pct_wip = (
        wip / len(subjects) * 100
        if subjects else 0
    )

    merges = sum(
        1 for s in subjects
        if s.startswith('Merge')
    )
    pct_merge = (
        merges / len(subjects) * 100
        if subjects else 0
    )

    all_text = ' '.join(bodies)
    file_line_refs = re.findall(
        r'\b\w+\.py:\d+(?:-\d+)?', all_text
    )
    gh_links = re.findall(
        r'https://github\.com/[^\s\)]+', all_text
    )

    claude_footer = sum(
        1 for b in bodies
        if 'claude-code' in b.lower()
    )

    return {
        'pct_wip': pct_wip,
        'pct_merge': pct_merge,
        'file_line_refs': len(file_line_refs),
        'gh_links': len(gh_links),
        'claude_footer': claude_footer,
    }


def find_example_commits(
    commits: list[dict],
    max_examples: int = 3,
) -> list[dict]:
    '''
    Pick representative example commits for the style
    guide — one simple (no body), one with bullets,
    one with section markers.

    '''
    examples: list[dict] = []
    found_simple = False
    found_bullets = False
    found_markers = False

    markers = [
        'Deats,', 'Also,', 'Other,', 'Further,',
    ]

    for c in commits:
        if len(examples) >= max_examples:
            break

        subj = c.get('subject', '')
        body = c.get('body', '').strip()

        # skip merges and WIP
        if (
            subj.startswith('Merge')
            or subj.startswith('WIP')
        ):
            continue

        if not found_simple and not body:
            examples.append(c)
            found_simple = True
        elif (
            not found_markers
            and body
            and any(m in body for m in markers)
        ):
            examples.append(c)
            found_markers = True
        elif (
            not found_bullets
            and body
            and ('\n- ' in body or body.startswith('- '))
        ):
            examples.append(c)
            found_bullets = True

    return examples


# -- style guide renderer ------------------------------------------

ABBREV_NAMES: dict[str, str] = {
    'msg': 'message',
    'bg': 'background',
    'ctx': 'context',
    'impl': 'implementation',
    'mod': 'module',
    'obvi': 'obviously',
    'tn': 'task name',
    'fn': 'function',
    'vs': 'versus',
    'bc': 'because',
    'var': 'variable',
    'prolly': 'probably',
    'ep': 'entry point',
    'OW': 'otherwise',
    'rn': 'right now',
    'sig': 'signal/signature',
    'deps': 'dependencies',
    'iface': 'interface',
    'subproc': 'subprocess',
    'tho': 'though',
    'ofc': 'of course',
    'env': 'environment',
    'osenv': 'OS environment',
    'dne': 'does not exist',
    'tf': 'the f...',
    'wtf': 'what the f...',
    'dunno': "don't know",
    'gonna': 'going to',
    'wanna': 'want to',
    'w/': 'with',
    'wo/': 'without',
}


def render_style_guide(
    repo_name: str,
    commits: list[dict],
    subj: dict,
    backticks: list,
    bodies: dict,
    lang: dict,
    special: dict,
    date_range: str,
    commit_count: int,
) -> str:
    '''
    Render a complete style-guide-reference.md from
    analysis results.

    '''
    lines: list[str] = []

    def emit(s: str = ''):
        lines.append(s)

    # -- header
    emit(
        f'# Commit Message Style Guide for `{repo_name}`'
    )
    emit()
    emit(
        f'Analysis based on {commit_count} recent'
        f' commits from the `{repo_name}` repository.'
    )
    emit()

    # -- core principles
    emit('## Core Principles')
    emit()
    emit(
        'Write commit messages that are technically'
        ' precise yet casual in'
    )
    emit(
        'tone. Use abbreviations and informal language'
        ' while maintaining'
    )
    emit('clarity about what changed and why.')
    emit()

    # -- subject line format
    emit('## Subject Line Format')
    emit()
    emit('### Length and Structure')
    emit(
        f'- Target: ~50 chars with a hard-max of 67.'
    )
    emit(
        f'- Use backticks around code elements'
        f' ({subj["pct_backticks"]:.1f}% of commits)'
    )
    if subj['pct_colons'] > 1:
        emit(
            f'- Colon usage ({subj["pct_colons"]:.1f}%)'
            f', mostly for file prefixes'
        )
    if subj['pct_question'] > 0.5:
        emit(
            f'- End with \'?\' for uncertain changes'
            f' (rare: {subj["pct_question"]:.1f}%)'
        )
    if subj['pct_exclaim'] > 0.5:
        emit(
            f'- End with \'!\' for important changes'
            f' (rare: {subj["pct_exclaim"]:.1f}%)'
        )
    emit()

    # -- opening verbs
    emit('### Opening Verbs (Present Tense)')
    emit()
    emit('Most common verbs from analysis:')

    verb_descriptions: dict[str, str] = {
        'Add': 'wholly new features/functionality',
        'Use': 'adopt new approach/tool',
        'Drop': 'remove code/feature',
        'Fix': 'bug fixes',
        'Move': 'relocate code',
        'Mv': 'relocate code (abbreviated)',
        'Adjust': 'minor tweaks',
        'Update': 'enhance existing feature',
        'Bump': 'dependency updates',
        'Rename': 'identifier changes',
        'Set': 'configuration changes',
        'Handle': 'add handling logic',
        'Raise': 'add error raising',
        'Pass': 'pass parameters/values',
        'Support': 'add support for something',
        'Hide': 'make private/internal',
        'Always': 'enforce consistent behavior',
        'Mk': 'make/create (abbreviated)',
        'Start': 'begin implementation',
        'Don\'t': 'prevent/avoid something',
        'Factor': 'refactoring',
        'Expose': 'make API public',
        'Extend': 'expand functionality',
        'Woops': 'acknowledge mistakes',
        'Refine': 'improve existing code',
        'Impl': 'implement (abbreviated)',
        'Port': 'migrate code',
        'Flip': 'toggle/switch',
    }

    top_verbs = [
        (v, c) for v, c in subj['verb_counts'][:25]
        if v and not v.startswith('Merge')
    ]
    for verb, count in top_verbs:
        pct = count / subj['total'] * 100
        desc = verb_descriptions.get(verb, '')
        if desc:
            emit(f'- `{verb}` ({pct:.1f}%) - {desc}')
        else:
            emit(f'- `{verb}` ({pct:.1f}%)')
    emit()

    # -- backtick usage
    emit('### Backtick Usage')
    emit()
    emit('Always use backticks for:')
    emit(
        '- Module names, class names, method names,'
        ' function names'
    )
    emit('- Decorators, exceptions, keywords')
    emit('- Variable names, complex expressions')
    emit()

    if backticks:
        top_terms = [
            f'`{term}`'
            for term, _ in backticks[:15]
        ]
        emit(
            f'Most backticked terms in {repo_name}:'
        )
        emit(', '.join(top_terms))
    emit()

    # -- examples (subject lines from data)
    example_subjects = [
        c['subject'] for c in commits
        if (
            'subject' in c
            and '`' in c['subject']
            and not c['subject'].startswith('Merge')
            and len(c['subject']) <= 55
        )
    ][:7]
    if example_subjects:
        emit('### Examples')
        emit()
        emit('Good subject lines:')
        emit('```')
        for s in example_subjects:
            emit(s)
        emit('```')
        emit()

    # -- body format
    emit('## Body Format')
    emit()
    emit('### General Structure')
    emit(
        f'- {bodies["pct_empty"]:.1f}% of commits'
        f' have no body (simple changes)'
    )
    emit('- Use blank line after subject')
    emit(
        '- Max line length: 67 display-columns'
        ' (fill width)'
    )
    emit(
        f'- Use `-` bullets for lists'
        f' ({bodies["pct_bullet_dash"]:.1f}%'
        f' of commits)'
    )
    if bodies['pct_bullet_star'] > 1:
        emit(
            f'- Rarely use `*` bullets'
            f' ({bodies["pct_bullet_star"]:.1f}%)'
        )
    emit()

    # -- section markers
    if bodies['section_markers']:
        emit('### Section Markers')
        emit()
        emit(
            'Use these markers to organize longer'
            ' commit bodies:'
        )
        for marker, count in bodies['section_markers']:
            if count > 0:
                emit(f'- `{marker}` ({count} occurrences)')
        emit()

    # -- abbreviations
    if lang['abbreviations']:
        emit('### Common Abbreviations')
        emit()
        emit('Use these freely (sorted by frequency):')
        for abbrev, count in lang['abbreviations']:
            meaning = ABBREV_NAMES.get(abbrev, '')
            if meaning:
                emit(
                    f'- `{abbrev}` ({count})'
                    f' - {meaning}'
                )
            else:
                emit(f'- `{abbrev}` ({count})')
        emit()

    # -- tone
    emit('### Tone and Style')
    emit()
    emit(
        '- Casual but technical'
    )
    if lang.get('tone_indicators'):
        for indicator, count in (
            lang['tone_indicators'].items()
        ):
            if indicator == '..':
                emit(
                    f'- Use `..` for trailing thoughts'
                    f' ({count} occurrences)'
                )
            elif indicator in ('Woops', 'woops'):
                emit(
                    f'- Use `{indicator},` to acknowledge'
                    f' mistakes ({count} uses)'
                )
            elif indicator == 'XD':
                emit(
                    f'- Use `XD` for humor'
                    f' ({count} uses)'
                )
            elif indicator == 'lol':
                emit(
                    f'- `lol` occasionally'
                    f' ({count} uses)'
                )
    emit(
        '- Show personality while being precise'
    )
    emit()

    # -- example bodies
    examples = find_example_commits(commits)
    if examples:
        emit('### Example Bodies')
        emit()
        for ex in examples:
            body = ex.get('body', '').strip()
            subj_line = ex.get('subject', '')
            if not body:
                emit('Simple (no body):')
                emit('```')
                emit(subj_line)
                emit('```')
            else:
                emit('Structured:')
                emit('```')
                emit(subj_line)
                emit()
                emit(body)
                emit('```')
            emit()

    # -- special patterns
    emit('## Special Patterns')
    emit()
    emit('### WIP Commits')
    emit(
        f'Rare ({special["pct_wip"]:.1f}%)'
        f' - avoid committing WIP if possible'
    )
    emit()
    emit('### Merge Commits')
    emit(
        f'Auto-generated ({special["pct_merge"]:.1f}%),'
        f" don't worry about style"
    )
    emit()
    if special['file_line_refs'] > 0:
        emit('### File References')
        emit(
            f'- File:line references used'
            f' {special["file_line_refs"]} times'
        )
        emit()
    if special['gh_links'] > 0:
        emit('### Links')
        emit(
            f'- GitHub links used sparingly'
            f' ({special["gh_links"]} total)'
        )
        emit('- Prefer code references over'
             ' external links')
        emit()

    # -- footer
    emit('## Footer')
    emit()
    emit(
        'The default footer should credit `claude`'
        ' (you) for helping generate'
    )
    emit('the commit msg content:')
    emit()
    emit('```')
    emit(
        '(this commit msg was generated in some part'
        ' by [`claude-code`][claude-code-gh])'
    )
    emit(
        '[claude-code-gh]:'
        ' https://github.com/anthropics/claude-code'
    )
    emit('```')
    emit()
    emit(
        'Further, if the patch was solely or in part'
        ' written'
    )
    emit('by `claude`, instead add:')
    emit()
    emit('```')
    emit(
        '(this patch was generated in some part by'
        ' [`claude-code`][claude-code-gh])'
    )
    emit(
        '[claude-code-gh]:'
        ' https://github.com/anthropics/claude-code'
    )
    emit('```')
    emit()

    # -- checklist
    emit('## Summary Checklist')
    emit()
    emit('Before committing, verify:')
    emit('- [ ] Subject line uses present tense verb')
    emit('- [ ] Subject line ~50 chars (hard max 67)')
    emit('- [ ] Code elements wrapped in backticks')
    emit(
        '- [ ] Body lines <=67 display-cols'
        ' (fill width)'
    )
    emit('- [ ] Abbreviations used where natural')
    emit('- [ ] Casual yet precise tone')
    emit(
        '- [ ] Section markers if body >3 paragraphs'
    )
    emit('- [ ] Technical accuracy maintained')
    emit()

    # -- metadata
    emit('## Analysis Metadata')
    emit()
    emit('```')
    emit(f'Source: {repo_name} repository')
    emit(f'Commits analyzed: {commit_count}')
    emit(f'Date range: {date_range}')
    emit(f'Analysis date: {date.today().isoformat()}')
    emit('```')
    emit()

    # -- credit footer
    emit('---')
    emit()
    emit(
        '(this style guide was generated by'
        ' [`claude-code`][claude-code-gh]'
    )
    emit('analyzing commit history)')
    emit()
    emit(
        '[claude-code-gh]:'
        ' https://github.com/anthropics/claude-code'
    )

    return '\n'.join(lines) + '\n'


# -- main -----------------------------------------------------------

def main():
    '''
    CLI entry point.

    '''
    parser = argparse.ArgumentParser(
        description=(
            'Generate a commit-message style guide'
            ' from git history'
        ),
    )
    parser.add_argument(
        'repo',
        help='Path to the git repository to analyze',
    )
    parser.add_argument(
        '--commits', '-n',
        type=int,
        default=500,
        help='Number of commits to analyze (default: 500)',
    )
    parser.add_argument(
        '--output', '-o',
        type=Path,
        help=(
            'Output file path (default: stdout). '
            'Typical: .claude/skills/commit-msg/'
            'style-guide-reference.md'
        ),
    )
    parser.add_argument(
        '--author',
        help=(
            'Filter commits to a specific author'
            ' pattern (passed to git log --author)'
        ),
    )

    args = parser.parse_args()
    repo_path: str = args.repo

    # validate repo
    check = subprocess.run(
        ['git', '-C', repo_path, 'rev-parse', '--git-dir'],
        capture_output=True,
    )
    if check.returncode != 0:
        print(
            f'Error: {repo_path} is not a git'
            f' repository',
            file=sys.stderr,
        )
        sys.exit(1)

    repo_name = get_repo_name(repo_path)
    print(
        f'Analyzing {args.commits} commits from'
        f' `{repo_name}`...',
        file=sys.stderr,
    )

    # export + parse
    raw = export_commits(
        repo_path,
        count=args.commits,
        author=args.author,
    )
    commits = parse_commits(raw)
    print(
        f'Parsed {len(commits)} commits',
        file=sys.stderr,
    )

    if not commits:
        print(
            'Error: no commits found',
            file=sys.stderr,
        )
        sys.exit(1)

    # analyze
    subj_analysis = analyze_subjects(commits)
    backtick_analysis = analyze_backticks(commits)
    body_analysis = analyze_bodies(commits)
    lang_analysis = analyze_language(commits)
    special_analysis = analyze_special_patterns(commits)
    date_range = get_date_range(commits)

    # render
    guide = render_style_guide(
        repo_name=repo_name,
        commits=commits,
        subj=subj_analysis,
        backticks=backtick_analysis,
        bodies=body_analysis,
        lang=lang_analysis,
        special=special_analysis,
        date_range=date_range,
        commit_count=len(commits),
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(guide)
        print(
            f'Style guide written to {args.output}',
            file=sys.stderr,
        )
    else:
        print(guide)


if __name__ == '__main__':
    main()
