#!/usr/bin/env python3
"""Print the last assistant reply of the current opencode session.

Companion extractor for the `claude-reply` nvim plugin's opencode
provider: when opencode's `editor_open` (ctrl+e) spawns nvim on its
prompt temp file, the plugin shells out here to fetch the last AI
reply so it can inject it as quoted-reference above the prompt.

Default route reads opencode's sqlite store directly (read-only,
~20ms; stdlib only). `--via-export` instead chains the built-in CLI
(`opencode session list` + `opencode export`) — slower (~1.2s, two
process spawns) but immune to storage-schema drift; kept as the
documented fallback should the direct query ever break.

Session choice: the most-recently-updated *top-level* session whose
`directory` is the given cwd or lives under it (opencode spawns the
editor with cwd = git worktree root, while the session may have been
started in a subdir).

Exit codes: 0 = reply on stdout; 3 = no session/reply found;
non-zero otherwise on hard errors.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile

DB_DEFAULT = os.path.expanduser(
    "~/.local/share/opencode/opencode-stable.db"
)


def parts_text(parts: list[dict]) -> str:
    """Join the text parts of one assistant message."""
    texts = [
        p.get("text", "")
        for p in parts
        if p.get("type") == "text" and p.get("text")
    ]
    return "\n\n".join(t.strip() for t in texts if t.strip())


def _pick_session(c: sqlite3.Cursor, cwd: str) -> str | None:
    row = c.execute(
        "select id from session"
        " where parent_id is null"
        "   and (directory = ? or directory like ? || '/%')"
        " order by time_updated desc limit 1",
        (cwd, cwd),
    ).fetchone()
    return row[0] if row else None


def list_sessions(db: str, cwd: str, all_dirs: bool) -> list[dict]:
    """Top-level sessions, newest first: {id, title, directory, ts}."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        c = con.cursor()
        q = (
            "select id, title, directory, time_updated from session"
            " where parent_id is null"
        )
        args: tuple = ()
        if not all_dirs:
            q += " and (directory = ? or directory like ? || '/%')"
            args = (cwd, cwd)
        q += " order by time_updated desc"
        return [
            {"id": i, "title": t, "directory": d, "ts": ts}
            for (i, t, d, ts) in c.execute(q, args).fetchall()
        ]
    finally:
        con.close()


def _msg_text(c: sqlite3.Cursor, mid: str) -> str:
    parts = [
        json.loads(d)
        for (d,) in c.execute(
            "select data from part"
            " where message_id = ? order by time_created",
            (mid,),
        )
    ]
    return parts_text(parts)


def via_db(db: str, cwd: str, sid: str | None = None) -> str | None:
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        c = con.cursor()
        sid = sid or _pick_session(c, cwd)
        if not sid:
            return None
        # newest assistant message with non-empty text parts.
        # NB fetchall(): `_msg_text` reuses this cursor — streaming the
        # outer rows would be clobbered by the inner execute.
        rows = c.execute(
            "select id from message"
            " where session_id = ?"
            "   and json_extract(data, '$.role') = 'assistant'"
            " order by time_created desc",
            (sid,),
        ).fetchall()
        for (mid,) in rows:
            txt = _msg_text(c, mid)
            if txt:
                return txt
        return None
    finally:
        con.close()


def via_db_list(db: str, cwd: str, sid: str | None = None) -> list[dict] | None:
    """All replies of the session as ordered turns.

    Mirrors the claude-transcript semantics: consecutive assistant
    messages between two user prompts form ONE logical turn. Each
    turn: {"text": ..., "ts": <epoch-ms of first msg>}.
    """
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        c = con.cursor()
        sid = sid or _pick_session(c, cwd)
        if not sid:
            return None
        turns: list[dict] = []
        texts: list[str] = []
        ts = None

        def close() -> None:
            nonlocal texts, ts
            if texts:
                turns.append({"text": "\n\n".join(texts), "ts": ts})
                texts, ts = [], None

        # fetchall(): same cursor-reuse hazard as `via_db` above
        rows = c.execute(
            "select id, json_extract(data, '$.role'), time_created"
            " from message where session_id = ?"
            " order by time_created",
            (sid,),
        ).fetchall()
        for mid, role, tc in rows:
            if role == "assistant":
                txt = _msg_text(c, mid)
                if txt:
                    texts.append(txt)
                    ts = ts if ts is not None else tc
            elif role == "user":
                close()
        close()
        return turns or None
    finally:
        con.close()


def via_export(cwd: str) -> str | None:
    # `session list` is cwd/project-scoped; first data row == most
    # recent. Rows: `<session-id>  <title>  <updated>`.
    out = subprocess.run(
        ["opencode", "session", "list"],
        capture_output=True, text=True, cwd=cwd, timeout=30,
    ).stdout
    sid = None
    for line in out.splitlines():
        tok = line.split()
        if tok and tok[0].startswith("ses_"):
            sid = tok[0]
            break
    if not sid:
        return None
    # NOTE: export stdout truncates on pipes (bun flush bug) — go via
    # a temp file.
    with tempfile.NamedTemporaryFile(
        mode="r", suffix=".json", delete=False
    ) as tf:
        path = tf.name
    try:
        with open(path, "w") as fh:
            subprocess.run(
                ["opencode", "export", sid],
                stdout=fh, stderr=subprocess.DEVNULL,
                cwd=cwd, timeout=60, check=True,
            )
        with open(path) as fh:
            data = json.load(fh)
    finally:
        os.unlink(path)
    for msg in reversed(data.get("messages", [])):
        info = msg.get("info", {})
        if info.get("role") != "assistant":
            continue
        txt = parts_text(msg.get("parts", []))
        if txt:
            return txt
    return None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cwd", default=os.getcwd())
    ap.add_argument("--db", default=DB_DEFAULT)
    ap.add_argument(
        "--via-export", action="store_true",
        help="use the opencode CLI (session list + export) instead of"
        " reading the sqlite store directly",
    )
    ap.add_argument(
        "--list", action="store_true",
        help="emit ALL replies of the session as a JSON array of"
        ' {"text", "ts"} turns (oldest first) instead of the last'
        " reply's text",
    )
    ap.add_argument(
        "--session", default=None, metavar="ID",
        help="target this exact session id instead of picking the"
        " most-recent one for --cwd",
    )
    ap.add_argument(
        "--sessions", action="store_true",
        help="emit the session list as a JSON array of"
        ' {"id", "title", "directory", "ts"} (newest first)',
    )
    ap.add_argument(
        "--all-dirs", action="store_true",
        help="with --sessions: list sessions of EVERY directory, not"
        " just --cwd's project",
    )
    args = ap.parse_args()

    cwd = os.path.realpath(args.cwd)
    if args.sessions:
        sessions = list_sessions(args.db, cwd, args.all_dirs)
        if not sessions:
            return 3
        json.dump(sessions, sys.stdout)
        return 0
    if args.list:
        turns = via_db_list(args.db, cwd, args.session)
        if not turns:
            return 3
        json.dump(turns, sys.stdout)
        return 0
    if args.via_export:
        txt = via_export(cwd)
    else:
        txt = via_db(args.db, cwd, args.session)
    if not txt:
        return 3
    sys.stdout.write(txt)
    return 0


if __name__ == "__main__":
    sys.exit(main())
