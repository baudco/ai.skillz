# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Complete saved dialog names for Xonsh's `ai.resume` command.

The Xontrib and source aliases share a contextual completer.
Read dialog metadata only when completing the name argument; use the
resume command's cwd and harness filters without resolving WKTs or
starting processes. Xonsh supplies parsed argument contexts and
replacement boundaries; completed names remain literal arguments.

'''

import json
import hashlib
from contextvars import ContextVar, Token
from pathlib import Path
import sqlite3
import sys
from types import ModuleType
from typing import Any
from xonsh.completers.tools import (
    contextual_command_completer,
    RichCompletion,
)
from xonsh.parsers.completion_context import CommandContext

# Source aliases load this file without installing a package.
if __package__ in (None, ''):
    source_root: str = str(Path(__file__).resolve().parent)
    source_key: str = (
        hashlib.sha256(source_root.encode()).hexdigest()
    )
    __package__ = '_aiskillz_source_' + source_key
    if __package__ not in sys.modules:
        source_package: ModuleType = ModuleType(__package__)
        source_package.__path__ = [source_root]
        sys.modules[__package__] = source_package

from . import dialogs
from .cli import _display_text

_resume_order: ContextVar[dict[str, int]|None] = ContextVar(
    'aiskillz_resume_order', default=None,
)


@contextual_command_completer
def complete_resume(command: CommandContext) -> tuple|set|None:
    '''
    Suggest complete dialog names at `ai.resume`'s selector position.

    Scan parsed arguments on both sides of the cursor for `--repo`,
    `-a` and `-b`. Option values and later positional arguments defer
    to other completers. Read `list_dialogs()` using the shell's
    environment so store overrides behave like `ai.dlogs`.
    Missing or invalid stores produce no completion diagnostics.
    Descriptions identify duplicate names; selection never chooses
    one dialog on behalf of `resume_target()`.
    `register_resume_completer()` records the alias argv because
    prompt-toolkit expands subprocess aliases before completion.

    '''
    from xonsh.built_ins import XSH

    alias: Any = (
        XSH.aliases.get('ai.resume')
        if XSH.aliases is not None else None
    )
    registered: Any = (
        XSH.ctx.get('_aiskillz_completer_argv')
        if XSH.ctx is not None else None
    )
    if registered is not None and alias != registered:
        return None
    arg: Any
    words: list[str|None] = [arg.value for arg in command.args]
    cursor: int = command.arg_index
    if command.command != 'ai.resume':
        if (
            not registered
            or words[:len(registered)] != registered
        ):
            return None
        # Prompt-toolkit expands subprocess aliases before parsing.
        # Match the current alias argv, then normalize its prefix.
        cursor -= len(registered) - 1
        words = ['ai.resume', *words[len(registered):]]
    if (
        cursor < 1
        or command.suffix
        or command.opening_quote not in ('', "'", '"')
    ):
        return None
    words.insert(cursor, None)
    value_options: set[str] = {
        '--repo', '-b', '--harness', '--id', '--cwd',
    }
    values: dict[str, str] = {}
    all_repos: bool = False
    selector_seen: bool = False
    completing_name: bool = False
    index: int = 1
    while index < len(words):
        word: str|None = words[index]
        if word in value_options:
            index += 1
            if (
                index >= len(words)
                or words[index] is None
            ):
                return None
            option: str = '--harness' if word == '-b' else word
            values[option] = words[index]
        elif word is None:
            completing_name = not selector_seen
            selector_seen = True
        elif word in ('-a', '--all-repos'):
            all_repos = True
        elif word in ('--dry-run', '-h', '--help'):
            pass
        elif word.startswith('--') and '=' in word:
            option: str
            value: str
            option, value = word.split('=', 1)
            if option not in value_options:
                return None
            values[option] = value
        elif word.startswith('-'):
            return None
        else:
            selector_seen = True
        index += 1
    if not completing_name or command.prefix.startswith('-'):
        return None

    environment: dict[str, str]|None = (
        XSH.env.detype() if XSH.env is not None else None
    )
    try:
        rows: list[dict] = dialogs.list_dialogs(
            path=None if all_repos else values.get('--repo', '.'),
            harness=values.get('--harness'),
            environ=environment,
        )
    except (
        OSError,
        ValueError,
        sqlite3.Error,
    ):
        return set()

    groups: dict[str, list[str]] = {}
    updated: dict[str, float] = {}
    row: dict
    for row in rows:
        name: str = row['name']
        if not name.startswith(command.prefix):
            continue
        did: str = row['id']
        if '--id' in values and did != values['--id']:
            continue
        harness: str = row['harness']
        cwd: str = row['cwd']
        groups.setdefault(name, []).append(
            f'{harness}:{did} @ {cwd}',
        )
        updated[name] = max(
            updated.get(name, 0), row.get('updated_at', 0),
        )
    sort_by: str = (environment or {}).get(
        'AI_RESUME_COMPLETION_SORT', 'last-update-time',
    )
    names: list[str] = sorted(
        groups, key=lambda name: (name.casefold(), name),
    )
    if sort_by != 'name':
        names.sort(key=lambda name: updated[name], reverse=True)
    result: list[RichCompletion] = []
    quote: str = command.opening_quote or "'"
    name: str
    for name in names:
        details: list[str] = groups[name]
        literal_injection: bool = (
            '$' in name or name.startswith('~')
        )
        if (
            literal_injection
            and command.closing_quote
            and not command.is_after_closing_quote
        ):
            # Leave the existing closing quote intact. These names
            # require replacing the whole argument with @(...).
            continue
        escaped: list[str] = []
        char: str
        for char in name:
            if char == quote:
                escaped.append('\\' + char)
            else:
                escaped.append(
                    json.dumps(char, ensure_ascii=True)[1:-1],
                )
        closing: str = (
            '' if command.closing_quote
            and not command.is_after_closing_quote else quote
        )
        value: str = (
            '@(' + repr(name) + ')'
            if literal_injection
            else quote + ''.join(escaped) + closing
        )
        result.append(RichCompletion(
            value,
            prefix_len=len(command.raw_prefix),
            display=_display_text(name),
            description=_display_text('; '.join(details)),
            append_closing_quote=False,
        ))
    item: RichCompletion
    index: int
    _resume_order.set({
        str(item): index for index, item in enumerate(result)
    })
    return result, len(command.raw_prefix)


def _install_completion_order(xsh: Any) -> None:
    '''
    Preserve dialog ranks through Xonsh's alphabetical final sort.

    Wrap `Completer.complete_from_context()` while this extension is
    loaded. A context-local rank mapping affects only results from
    `complete_resume()` in that invocation; other completers retain
    their ordering. Save the prior method for ownership-aware unload.

    '''
    from xonsh.completer import Completer

    current: Any = Completer.complete_from_context
    if current is not xsh.ctx.get('_aiskillz_sort_wrapper'):
        xsh.ctx['_aiskillz_sort_original'] = current
    original: Any = xsh.ctx['_aiskillz_sort_original']

    def ordered_completions(
        self: Any,
        completion_context: Any,
        old_completer_args: Any = None,
    ) -> tuple:
        '''
        Restore this invocation's dialog order after Xonsh sorting.

        '''
        token: Token = _resume_order.set(None)
        try:
            results: tuple
            prefix: int
            results, prefix = original(
                self, completion_context, old_completer_args,
            )
            order: dict[str, int]|None = _resume_order.get()
            item: Any
            if (
                order
                and all(str(item) in order for item in results)
            ):
                results = tuple(sorted(
                    results, key=lambda item: order[str(item)],
                ))
            return results, prefix
        finally:
            _resume_order.reset(token)

    Completer.complete_from_context = ordered_completions
    xsh.ctx['_aiskillz_sort_wrapper'] = ordered_completions


def register_resume_completer(xsh: Any) -> None:
    '''
    Install name completion before fallback command/path completers.

    `_load_xontrib_()` and `aliases.xsh` call this function. Retain
    the original completer across repeated loads so unloading can
    restore a prior registration under the same registry key.

    '''
    registry: Any = getattr(xsh, 'completers', None)
    if registry is None:
        return
    _install_completion_order(xsh)
    key: str = 'aiskillz_resume'
    if (
        '_aiskillz_completer_command' not in xsh.ctx
        or
        registry.get(key) != xsh.ctx['_aiskillz_completer_command']
    ):
        xsh.ctx['_aiskillz_completer_previous'] = registry.get(key)
    xsh.ctx['_aiskillz_completer_command'] = complete_resume
    alias: Any = xsh.aliases.get('ai.resume')
    xsh.ctx['_aiskillz_completer_argv'] = (
        list(alias) if isinstance(alias, list) else None
    )
    remaining: dict = dict(registry)
    remaining.pop(key, None)
    registry.clear()
    registry[key] = complete_resume
    registry.update(remaining)


def unregister_resume_completer(xsh: Any) -> None:
    '''
    Restore a prior completer while preserving user replacements.

    `_unload_xontrib_()` calls this alongside alias restoration.
    Remove this extension's registration when none existed before
    loading; always release its saved context entries.

    '''
    from xonsh.completer import Completer

    registry: Any = getattr(xsh, 'completers', None)
    wrapper: Any = xsh.ctx.pop('_aiskillz_sort_wrapper', None)
    original: Any = xsh.ctx.pop('_aiskillz_sort_original', None)
    if (
        wrapper is not None
        and Completer.complete_from_context is wrapper
    ):
        Completer.complete_from_context = original
    command: Any = xsh.ctx.pop('_aiskillz_completer_command', None)
    previous: Any = xsh.ctx.pop('_aiskillz_completer_previous', None)
    xsh.ctx.pop('_aiskillz_completer_argv', None)
    if (
        registry is not None
        and registry.get('aiskillz_resume') is command
    ):
        if previous is None:
            registry.pop('aiskillz_resume', None)
        else:
            registry['aiskillz_resume'] = previous
