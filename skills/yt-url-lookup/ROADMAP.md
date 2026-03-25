# Media Skills Roadmap

Vision for a family of media-related Claude Code skills
that eventually consolidate into a standalone Python
project + xontrib for terminal-native music discovery,
download, indexing, and social sharing.

## Current State

```
~/.claude/skills/yt-url-lookup/
    SKILL.md        # reverse-lookup local files -> YT URLs
    ROADMAP.md      # (this file)
```

## Planned Sibling Skills

### `yt-dl-audio` — download audio from video URLs

Extract and download audio tracks from YouTube (or
`music.youtube.com`) video URLs with configurable quality
and format preferences.

**Core workflow**:
- Accept URL(s) as args (single, list, or playlist)
- Select audio format/quality (opus preferred, flac for
  lossless, mp3 for compat)
- Download via `yt-dlp` with appropriate `--audio-format`,
  `--audio-quality`, `--embed-metadata` flags
- Name files using configurable output template
  (default: `%(title)s.%(channel)s.%(ext)s`)
- Embed video ID in metadata for future reverse-lookup
- Write download receipt to an `INDEX.md` or append to
  existing one (reuse `/yt-url-lookup` index format)

**Key `yt-dlp` flags to codify**:
```
-x --audio-format opus
--audio-quality 0
--embed-metadata --embed-thumbnail
--output "%(title)s.%(channel)s.%(ext)s"
--write-info-json
```

**Quality presets**:

| Preset | Format | Bitrate | Use case |
|--------|--------|---------|----------|
| `best` | opus | ~160kbps VBR | default, transparent quality |
| `lossless` | flac | ~1000kbps | archival, DJ use |
| `portable` | mp3 | 320kbps CBR | device compat |
| `tiny` | opus | ~64kbps | spoken word, podcasts |

**Future module**: `download.py`

---

### `audio-quality-check` — analyze local audio quality

Inspect local audio files for actual encoding quality,
detect transcodes (lossy->lossy re-encodes), and flag
files that claim higher quality than they deliver.

**Core workflow**:
- Scan directory for audio files (reuse inventory from
  `/yt-url-lookup` Phase 1a)
- For each file, extract:
  - Codec, container, sample rate, bit depth
  - Bitrate (average and peak)
  - Spectral analysis: frequency cutoff detection
    (a 128kbps mp3 re-encoded to flac still cuts off
    at ~16kHz)
- Flag suspicious files:
  - `flac` with spectral cutoff below 20kHz (likely
    transcode from lossy source)
  - `opus`/`mp3` with very low bitrate for the content
    type (e.g. <96kbps for music)
  - Mismatched container vs actual codec
- Generate quality report as markdown table

**Tools needed**: `ffprobe` (or `sox`/`mediainfo`),
`python3` with `numpy` for spectral analysis (or
`sox --stat`).

**Future modules**: `quality.py`, `spectral.py`

---

### `beet-import` — index and tag with beets

Bridge between the raw `yt-dlp` rips and a properly
tagged, organized music library using
[beets](https://beets.io).

**Core workflow**:
- Read `INDEX.md` for file<->URL mappings
- Extract metadata from YouTube info-json files
  (if saved by `/yt-dl-audio`)
- Map to beets fields: `artist`, `album` (set/event
  name), `title`, `date`, `comments` (source URL)
- Import into beets library with `beet import`
- Apply beets plugins: `fetchart`, `lyrics`,
  `lastgenre`, `acousticbrainz`
- Handle the "live set" genre: these are not albums;
  they need custom beets config for
  `artist - event @ venue YYYY` naming

**Beets config fragment**:
```yaml
paths:
  default: $artist/$album/$title
  comp: Various Artists/$album/$title
  # custom path for live sets
  live_set: Live Sets/$artist/$album%if{$venue, @ $venue}
```

**Future modules**: `beets_bridge.py`, `metadata.py`

---

### `yt-music-search` — find music on YouTube

The inverse of `/yt-url-lookup`: given an artist, track,
or set description, search YouTube/YouTube Music and
present results for the user to pick from.

**Core workflow**:
- Accept free-text query (artist name, "boiler room
  set", event name, etc.)
- Search via `yt-dlp ytsearch` and/or YouTube Music API
- Present results with duration, channel, view count,
  upload date
- User selects one or more; hand off to `/yt-dl-audio`
  for download
- Optionally chain: search -> download -> quality-check
  -> beet-import in a single invocation

**Future module**: `discover.py`

## The Xontrib: `xontrib-ytm`

All skills consolidate into a Python package exposing
xonsh commands for terminal-native music workflow:

```
xontrib-ytm/
    xontrib/ytm/
        __init__.py         # xontrib loader
        commands.py         # xonsh command registrations
    ytm/
        __init__.py         # library entry point
        inventory.py        # scan, parse filenames
        patterns.py         # filename regex, ID extraction
        db.py               # URL database parsers
        search.py           # YT search, query construction
        download.py         # yt-dlp wrapper, presets
        quality.py          # audio quality analysis
        spectral.py         # frequency cutoff detection
        beets_bridge.py     # beets import/tagging
        discover.py         # YT Music search/browse
        index.py            # INDEX.md generation
        metadata.py         # info-json / tag extraction
        bot.py              # chat bot integration
    tests/
    pyproject.toml
```

### Xonsh commands

```python
# reverse-lookup local files
ytm index ~/music/live_sets

# search YouTube Music
ytm search "four tet boiler room"

# download with quality preset
ytm dl --preset best "https://youtube.com/watch?v=..."

# check quality of local files
ytm check ~/music/live_sets/deewee/

# import into beets
ytm beet-import ~/music/live_sets/

# full pipeline: search -> pick -> download -> check -> tag
ytm grab "floating points boiler room 5 hour"
```

### Config (`~/.config/ytm/config.toml`)

```toml
[defaults]
audio_format = 'opus'
quality_preset = 'best'
output_template = '%(title)s.%(channel)s.%(ext)s'
embed_metadata = true
embed_thumbnail = true
write_info_json = true

[paths]
library = '~/music'
live_sets = '~/music/yt_rips/live_sets'
downloads = '~/music/yt_rips/incoming'

[beets]
config = '~/.config/beets/config.yaml'
auto_import = false

[bot]
enabled = false
# see [bot] section below
```

## Chat Bot Integration

The end goal: a bot that lurks in group chats (matrix,
signal, telegram, IRC) and reacts to music-related
conversation by offering to find/download/share tracks.

### How it works

1. **Passive listening**: bot watches for messages
   containing YouTube URLs, artist names, "have you
   heard", "this set is fire", etc.
2. **URL detection**: when someone drops a YT link, bot
   auto-indexes it (runs `/yt-url-lookup` logic) and
   optionally downloads
3. **Conversational search**: "anyone have that four tet
   set from lost village?" -> bot searches its local
   index + YouTube, offers results
4. **Share pipeline**: bot can upload audio files to
   the chat or provide a link to a self-hosted media
   server (e.g. navidrome, funkwhale)
5. **Group library**: the bot maintains a shared index
   across the group, deduplicating and tagging

### Bot config

```toml
[bot]
enabled = true
platform = 'matrix'       # matrix | signal | telegram
room_ids = ['!abc:matrix.org']
trigger_patterns = [
    'youtube\.com/watch',
    'youtu\.be/',
    'music\.youtube\.com',
    'anyone have',
    'looking for.*set',
    'this (set|mix) is',
]
auto_download = false      # require confirmation
auto_share = false         # require confirmation
max_file_size = '500MB'
```

**Future modules**: `bot.py`, `bot_matrix.py`,
`bot_signal.py`

## Migration Path: Skills -> Package

The progression from Claude Code skills to standalone
package:

```
Phase 1 (now):    Skills in ~/.claude/skills/
                  - yt-url-lookup ✓
                  - yt-dl-audio (next)
                  - audio-quality-check
                  - beet-import

Phase 2:          Extract Python snippets from SKILL.md
                  files into a proper package structure
                  under a new repo
                  - Each skill's "Future module" annotations
                    map directly to package modules
                  - Skills become thin wrappers that invoke
                    the library

Phase 3:          Xontrib wrapping the library
                  - xonsh commands delegating to library
                  - config via TOML
                  - shell completions

Phase 4:          Bot integration
                  - matrix/signal/telegram adapters
                  - event loop for passive listening
                  - shared group library state
```

## Dependency Stack

```
yt-dlp              # YouTube interaction (search, dl)
mutagen             # audio metadata read/write
beets               # library management (optional)
numpy               # spectral analysis (optional)
xonsh               # shell integration (optional)
matrix-nio          # matrix bot (optional)
# or
python-telegram-bot # telegram bot (optional)
```

Core (`yt-dlp` + `mutagen`) is the only hard
requirement. Everything else is opt-in via extras:

```toml
[project.optional-dependencies]
quality = ['numpy']
beets = ['beets']
xonsh = ['xonsh']
matrix = ['matrix-nio']
telegram = ['python-telegram-bot']
all = ['numpy', 'beets', 'xonsh', 'matrix-nio']
```
