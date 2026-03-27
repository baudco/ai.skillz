---
name: yt-url-lookup
description: >
  Reverse-lookup local audio files to their YouTube source
  URLs via filename parsing, existing URL databases, and
  yt-dlp search. Generate an INDEX.md mapping.
argument-hint: "[DIR] [--rescan]"
disable-model-invocation: true
allowed-tools:
  - Bash(yt-dlp *)
  - Bash(python3 *)
  - Bash(date *)
  - Bash(ls *)
  - Read
  - Grep
  - Glob
  - Write
  - Edit
---

Reverse-lookup local audio files (typically `yt-dlp` rips)
to their YouTube source video URLs. Scan a directory tree,
resolve as many files as possible from embedded video IDs
and existing URL databases, then search YouTube for the
rest. Write an `INDEX.md` with the complete mapping.

# Arguments

| Arg | Default | Purpose |
|-----|---------|---------|
| `DIR` | `.` (cwd) | root directory to scan |
| `--rescan` | off | ignore existing `INDEX.md`, rebuild from scratch |

When invoked as `/yt-url-lookup` with no args, use the
current working directory. When invoked as
`/yt-url-lookup ~/music/live_sets`, scan that tree.

# Phase 0: Prerequisites

0. **Check `yt-dlp`**: run `which yt-dlp`. If missing,
   STOP and tell the user:
   > `yt-dlp` is not installed. Install it via
   > `pip install yt-dlp` or your package manager.

1. **Detect target directory**: parse the argument for
   `DIR` (defaults to cwd). Confirm it exists with
   `ls DIR`.

2. **Check for `--rescan`**: if present, existing
   `INDEX.md` entries are ignored (but other URL
   databases like `urls.toml` are still consulted).

Report: "Scanning `<DIR>` for audio files..."

# Phase 1: Inventory

> Future module mapping: `inventory.py`, `patterns.py`,
> `db.py`

## 1a. Discover audio files

Glob recursively for these extensions:

```
**/*.opus
**/*.flac
**/*.mp3
**/*.m4a
**/*.ogg
**/*.wav
```

Store results as a list of relative paths (relative to
`DIR`). Sort alphabetically.

## 1b. Load existing URL databases

Scan the directory tree for files that contain known
URL mappings. Parse each format:

**`INDEX.md`** (if exists and not `--rescan`):
- Look for markdown table rows matching
  `| \`filename\` | https://...youtube... |`
- Extract `{filename: url}` pairs

**`urls.toml`**:
- Parse TOML; each key maps to an array of URL strings
- Comments above URLs often describe the content
- Extract all YouTube URLs and their video IDs

**`urls*.md`** (e.g. `urls_from_chatgpt_dnks.md`):
- Parse markdown tables for `| Title | URL |` columns
- Match titles to filenames via substring overlap

For every URL found, extract the video ID:

```python
import re

def extract_vid_from_url(url: str) -> str | None:
    '''Extract YouTube video ID from a URL.'''
    m = re.search(
        r'(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})',
        url,
    )
    return m.group(1) if m else None
```

Build two lookup structures:
- `by_vid_id: dict[str, str]` — video_id -> full URL
- `by_filename: dict[str, str]` — filename fragment -> URL

## 1c. Extract video IDs from filenames

For each audio file, try to extract an embedded YouTube
video ID using these patterns (in priority order):

```python
import re

PATTERNS = [
    # [VIDEO_ID] in filename
    re.compile(r'\[([A-Za-z0-9_-]{11})\]'),
    # -VIDEO_ID.ChannelOrExt
    re.compile(r'-([A-Za-z0-9_-]{11})\.'),
]

def extract_video_id(filename: str) -> str | None:
    '''
    Extract a YouTube video ID embedded in a
    filename. Return None if not found.

    '''
    for pat in PATTERNS:
        m = pat.search(filename)
        if m:
            candidate = m.group(1)
            # Reject candidates that look like
            # words or track numbers
            if (
                candidate.isalpha()
                or candidate.isdigit()
            ):
                continue
            return candidate
    return None
```

Examples of what this catches:
- `Title [Am-vGoDu-kk].flac` -> `Am-vGoDu-kk`
- `Title-rkNnWtG5pyQ.IDBR.opus` -> `rkNnWtG5pyQ`

## 1d. Cross-reference and classify

For each audio file, resolve in this priority order:

1. **Embedded ID**: if `extract_video_id()` returns a
   hit, mark `resolved` with
   `https://www.youtube.com/watch?v=<ID>`
2. **Existing INDEX.md**: if filename appears in parsed
   INDEX.md entries, mark `resolved`
3. **URL databases**: if filename fragments match a
   known URL from `urls.toml` or `urls*.md`, mark
   `resolved`
4. Otherwise, mark `needs_search`

Present an inventory summary to the user:

```
Inventory complete:
- 76 audio files found
- 5 with embedded video IDs
- 31 matched in existing databases
- 40 need YouTube search
```

# Phase 2: Search

> Future module mapping: `search.py`

## 2a. Build search queries

For each `needs_search` file, construct a YouTube search
query from the filename:

```python
import re

AUDIO_EXTS = re.compile(
    r'\.(opus|flac|mp3|m4a|ogg|wav)_?$'
)
PREFIX = re.compile(r'^(live_sets?|NA)\.')
TRACK_NUM = re.compile(r'^\d{1,3}[\.\-]')

def build_query(filename: str) -> str:
    '''
    Build a YouTube search query from an audio
    filename by stripping yt-dlp naming artifacts.

    '''
    name = filename

    # 1. Strip extension
    name = AUDIO_EXTS.sub('', name)

    # 2. Strip prefix (live_set., NA., NNN.)
    name = PREFIX.sub('', name)
    name = TRACK_NUM.sub('', name)

    # 3. Strip channel suffix
    #    yt-dlp names files as Title.Channel.ext
    #    so the last dot-segment is the channel.
    #    Only strip if there are 2+ dots remaining
    #    and the "title" portion is substantial.
    parts = name.rsplit('.', 1)
    if len(parts) == 2 and len(parts[0]) > 10:
        # Keep the channel name available for
        # refinement searches (step 2d)
        channel = parts[1]
        name = parts[0]
    else:
        channel = None

    # 4. Normalize special characters
    name = name.replace('_', ' ')
    for ch in ('｜', '⧸', '：', '⚡'):
        name = name.replace(ch, ' ')
    name = name.replace('@', '')
    name = re.sub(r'\s+', ' ', name).strip()

    return name, channel
```

**Examples**:

| Filename | Query | Channel |
|----------|-------|---------|
| `live_set.Four Tet live from Lost Village 2025.Four Tet.opus` | `Four Tet live from Lost Village 2025` | `Four Tet` |
| `NA.Bolis Pupul @TheLotRadio 08-08-2024.The Lot Radio.opus` | `Bolis Pupul TheLotRadio 08-08-2024` | `The Lot Radio` |
| `live_set.bolispupul_dourfestkioskradio_20230529.opus` | `bolispupul dourfestkioskradio 20230529` | `None` |
| `002.2manyDJs - Live @ Primavera Fauna, Santiago, Chile - 2014-11-22.Get Off The Speakers.opus` | `2manyDJs - Live @ Primavera Fauna, Santiago, Chile - 2014-11-22` | `Get Off The Speakers` |

## 2b. Execute batch searches

Search YouTube one query at a time via `yt-dlp`:

```python
import subprocess

def search_youtube(
    query: str,
    n: int = 1,
) -> list[dict] | None:
    '''
    Search YouTube for a query via yt-dlp.
    Return list of {id, title, channel} dicts.

    '''
    try:
        result = subprocess.run(
            [
                'yt-dlp',
                '--print',
                '%(id)s\t%(title)s\t%(channel)s',
                f'ytsearch{n}:{query}',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return None

    if result.returncode != 0 or not result.stdout.strip():
        return None

    hits = []
    for line in result.stdout.strip().split('\n'):
        parts = line.split('\t', 2)
        if len(parts) == 3:
            hits.append({
                'id': parts[0],
                'title': parts[1],
                'channel': parts[2],
            })
    return hits or None
```

Run all searches in a single `python3` script invocation.
Collect results into a mapping:
`{relative_path: {id, title, channel, confidence}}`.

## 2c. Validate results

For each search result, compare the returned title and
channel against the original filename to score confidence:

```python
def normalize(s: str) -> set[str]:
    '''Tokenize and lowercase for comparison.'''
    s = s.lower()
    s = re.sub(r'[^\w\s]', ' ', s)
    return {
        w for w in s.split()
        if len(w) > 2
    }

def score_match(
    query: str,
    result_title: str,
    result_channel: str,
) -> float:
    '''
    Score 0.0-1.0 how well a search result
    matches the original query.

    '''
    q_tokens = normalize(query)
    r_tokens = (
        normalize(result_title)
        | normalize(result_channel)
    )
    if not q_tokens:
        return 0.0
    overlap = q_tokens & r_tokens
    return len(overlap) / len(q_tokens)
```

Classification:
- score >= 0.5 -> `resolved` (confident match)
- score >= 0.3 -> `?` (uncertain, queue for refinement)
- score < 0.3 -> `??` (likely wrong result)

## 2d. Refine uncertain matches

For files marked `?` or `??`, retry with refined queries:

1. **Append channel**: if `build_query()` stripped a
   channel suffix, re-search with
   `"QUERY CHANNEL_NAME"`
2. **Top-3 search**: use `ytsearch3:` and pick the
   result with the highest `score_match()`
3. **Date/year focus**: if the filename contains a year
   (4 digits), ensure it's in the query

If after refinement the score is still < 0.3, mark as
`??` and move on.

**Present all search results to the user** for review
before proceeding to index generation. Format as a table:

```
| File | Query | Result Title | URL | Conf |
|------|-------|-------------|-----|------|
| ... | ... | ... | ... | OK/? /?? |
```

Wait for user confirmation before writing INDEX.md.

# Phase 3: Index Generation

> Future module mapping: `index.py`

## 3a. Merge with existing INDEX.md

If `DIR/INDEX.md` exists and `--rescan` is NOT set:
- Parse existing entries into `{filename: url}`
- Merge: new entries are added, existing entries are
  preserved
- If a file has a NEW url that differs from the existing
  one, flag it for user review:
  > `filename.opus`: existing URL differs from new
  > search result. Keep existing / use new / skip?

If `--rescan` IS set, start fresh.

## 3b. Detect duplicates

Files with identical basenames appearing in multiple
directories (e.g. `deewee/` and `from_xps/deewee/`)
should:
- All be listed with their URL (no suppression)
- Be counted once in the "unique sets" summary tally

## 3c. Write INDEX.md

Output format:

```markdown
# <Dir Name> - YouTube URL Index

> Reverse lookup of local audio files to their source
> YouTube videos.
> Generated <DATE> via `/yt-url-lookup` skill + `yt-dlp`
> search.

## Legend

- `?` = uncertain match / best guess
- `??` = unable to find source URL

---

## Root (`./`)

| File | YouTube URL |
|------|------------|
| `filename.opus` | https://www.youtube.com/watch?v=XXXXXXXXXXX |

---

## `subdir/`

| File | YouTube URL |
|------|------------|
| `another.flac` | https://www.youtube.com/watch?v=YYYYYYYYYYY |
| `uncertain.opus` | https://www.youtube.com/watch?v=ZZZZZZZZZZZ `?` |
| `unknown.opus` | `??` (reason) |

---

## Summary

- **Total audio files**: N
- **Unique sets with URLs found**: N
- **Uncertain** (`?`): N
  - list...
- **Unresolved** (`??`): N
  - list...
```

Sections are generated per subdirectory, sorted
alphabetically. Only directories containing audio files
get a section. Nested subdirectories use heading level 3
(`###`).

## 3d. Credit footer

Append to the end of INDEX.md:

```markdown
> (this index was generated in some part by
> [`claude-code`][claude-code-gh])
> [claude-code-gh]: https://github.com/anthropics/claude-code
```

# Error Handling

| Error | Action |
|-------|--------|
| `yt-dlp` not installed | STOP with install instructions |
| Network failure | retry once after 5s; if still failing mark `??` with `(network error)` and continue |
| HTTP 429 (rate limit) | exponential backoff: 5s, 15s, 45s; after 3 failures pause and ask user |
| No audio files found | report "no audio files found in DIR" and exit |
| Malformed INDEX.md | warn user, offer to rebuild (`--rescan`) |
| `?` in filename | treat as literal character (user uncertainty about event name); escape in search queries |

# Filename Patterns Reference

Observed naming conventions in yt-dlp audio rips:

| Pattern | Example | Prefix | Title | Channel |
|---------|---------|--------|-------|---------|
| yt-dlp default | `live_set.Title Here.Channel Name.opus` | `live_set` | `Title Here` | `Channel Name` |
| Embedded ID (hyphen) | `Title-VIDEO_ID.Channel.ext` | varies | `Title` | `Channel` |
| Embedded ID (bracket) | `Title [VIDEO_ID].ext` | varies | `Title` | none |
| Numbered | `002.Title.Channel.opus` | `002` | `Title` | `Channel` |
| NA prefix | `NA.Title.Channel.opus` | `NA` | `Title` | `Channel` |
| Manual underscore | `live_set.artist_venue_date.ext` | `live_set` | underscore-encoded | none |
| Dash-separated | `NN-Title-Channel.flac` | `NN` | `Title` | `Channel` |
| Plural prefix | `live_sets.Title.Channel.opus` | `live_sets` | `Title` | `Channel` |

The channel suffix is the last `.`-separated segment
before the file extension. This follows `yt-dlp`'s
default `%(title)s.%(channel)s.%(ext)s` output template.

For manually-named files (underscore-separated, no dots
in the title), there is no channel suffix; the entire
stem after the prefix is the title.

# Future: Python Library Structure

This skill's algorithm maps to a standalone Python
package for use in a xontrib:

```
yt_url_lookup/
    __init__.py       # CLI entry point
    inventory.py      # Phase 1: scan, parse, cross-ref
    patterns.py       # Filename regex patterns, ID extraction
    db.py             # URL database parsers (toml, md tables)
    search.py         # Phase 2: query construction, yt-dlp,
                      #   validation, refinement
    index.py          # Phase 3: merge, format, write INDEX.md
```

Each inline Python snippet in this skill is annotated
with its target module for straightforward extraction.
