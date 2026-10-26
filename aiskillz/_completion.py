# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.

'''
Adapt Xonsh's Tab completion to saved `ai.resume` dialog names.

The normal path is `ai.resume -b cx Wo<Tab>`:
- Xonsh parses the cursor position into `CommandContext`.
- `complete_resume()` reads matching dialogs and quotes their names.
- `RichCompletion` carries insertion text and descriptive metadata.
- `_install_completion_order()` restores recency order after Xonsh's
  final alphabetical sort. Other commands keep Xonsh's own ordering.

Both `xontrib load aiskillz` and `source aliases.xsh` register this
adapter. Completion reads metadata; it never starts a harness or
chooses a worktree. `resume_target()` still resolves the chosen name.

'''

import json
import hashlib
from collections.abc import Callable
from contextvars import (
    ContextVar,
    Token,
)
from pathlib import Path
import sqlite3
import sys
from types import ModuleType
from typing import cast

from xonsh.built_ins import XonshSession
from xonsh.completer import Completer
from xonsh.completers.tools import (
    contextual_command_completer,
    RichCompletion,
)
from xonsh.parsers.completion_context import (
    CommandArg,
    CommandContext,
    CompletionContext,
)

# `source /checkout/aliases.xsh` lets a shell try an arbitrary
# checkout without repinning its installed package. runpy supplies no
# package identity, but the relative imports below need one. A
# private module name per source directory keeps those imports in the
# selected checkout even when another editable aiskillz installation
# is already imported. This is a source-loader boundary, not an
# installed namespace package.
if __package__ in (
    None,
    '',
):
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


# Xonsh returns (candidates, replacement-prefix length). Its legacy
# completer arguments are passed through unchanged; this adapter uses
# CompletionContext instead of interpreting that older positional
# API.
type CompletionBatch = tuple[tuple[str|RichCompletion, ...], int]
type CompletionMethod = Callable[
    [
        Completer,
        CompletionContext|None,
        tuple|None,
    ],
    CompletionBatch,
]

# `complete_resume()` knows recency, but Xonsh sorts again afterward.
# Pass that invocation's rendered-string -> rank mapping to our
# wrapper around Completer.complete_from_context(). ContextVar tokens
# isolate nested calls: the wrapper clears the value on entry and
# restores the prior value on exit, including exceptions. No dialog
# data is cached.
_resume_order: ContextVar[dict[str, int]|None] = ContextVar(
    'aiskillz_resume_order',
    default=None,
)


@contextual_command_completer
def complete_resume(
    command: CommandContext,
) -> tuple[list[RichCompletion], int]|set[str]|None:
    '''
    Suggest names only where `ai.resume` expects its dialog selector.

    - Parse filters on either side of the cursor, including `--x=y`.
    - Return None outside our argument: Xonsh may try other
      completers.
    - Return an empty set on metadata errors: Tab stays quiet.
    - Use Xonsh's current environment to select metadata directories
      such as CODEX_HOME and OPENCODE_DATA_DIR, just like `ai.dlogs`.
    - Keep duplicate names as choices with descriptive harness/ID/cwd
      text; completion never decides which dialog to resume.

    Prompt-toolkit expands subprocess aliases before parsing. The
    argv saved by `register_resume_completer()` lets us recognize
    that expanded form as well as the literal `ai.resume` command.

    '''
    from xonsh.built_ins import XSH

    alias: object = None
    if XSH.aliases is not None:
        alias = XSH.aliases.get('ai.resume')

    registered: list[str]|None = None
    if XSH.ctx is not None:
        # This private context entry is written only by our register
        # function. Other context entries belong to user shell code.
        registered = cast(
            list[str]|None,
            XSH.ctx.get('_aiskillz_completer_argv'),
        )

    if registered is not None and alias != registered:
        # The user replaced the alias after registration. Do not
        # apply ai.resume argument rules to the replacement command.
        return None

    arg: CommandArg
    words: list[str|None] = [arg.value for arg in command.args]
    cursor: int = command.arg_index

    if command.command != 'ai.resume':
        if not registered or words[:len(registered)] != registered:
            # Neither the literal command nor our expanded argv
            # prefix.
            return None

        # Example: `python -m aiskillz resume Wo` becomes `ai.resume
        # Wo`. Adjust the cursor by the number of removed argv words.
        cursor -= len(registered) - 1
        words = [
            'ai.resume',
            *words[len(registered):],
        ]

    if (
        cursor < 1
        or command.suffix
        or command.opening_quote not in (
            '',
            "'",
            '"',
        )
    ):
        # Leave command-name completion, mid-word edits and
        # unsupported Python quote prefixes to Xonsh; replacing those
        # loses text.
        return None

    # CommandContext.args omits the argument currently being
    # completed. Insert a sentinel so parsing both sides of the
    # cursor can tell an option value apart from the single
    # positional dialog selector.
    words.insert(cursor, None)
    value_options: set[str] = {
        '--repo',
        '-b',
        '--harness',
        '--id',
        '--cwd',
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
            if index >= len(words) or words[index] is None:
                # The cursor is an option's value, or the value is
                # absent. Dialog names are not valid suggestions
                # here.
                return None

            option: str = word
            if word == '-b':
                option = '--harness'
            values[option] = words[index]

        elif word is None:
            completing_name = not selector_seen
            selector_seen = True
        elif word in (
            '-a',
            '--all-repos',
        ):
            all_repos = True
        elif word in (
            '--dry-run',
            '-h',
            '--help',
        ):
            pass
        elif word.startswith('--') and '=' in word:
            option: str
            value: str
            option, value = word.split('=', 1)
            if option not in value_options:
                # Unknown options have unknown arity. Stop rather
                # than guess which later word is the dialog selector.
                return None

            values[option] = value

        elif word.startswith('-'):
            # This may be an incomplete flag; let flag completion
            # run.
            return None
        else:
            selector_seen = True

        index += 1

    if not completing_name or command.prefix.startswith('-'):
        # A dialog selector already exists, or the cursor starts a
        # flag. We own neither later positionals nor option names.
        return None

    environment: dict[str, str]|None = None
    if XSH.env is not None:
        environment = XSH.env.detype()

    repo: str|None = values.get('--repo', '.')
    if all_repos:
        repo = None

    try:
        rows: list[dict] = dialogs.list_dialogs(
            path=repo,
            harness=values.get('--harness'),
            environ=environment,
        )

    except (
        OSError,
        ValueError,
        sqlite3.Error,
    ):
        # Completion is a quiet lookup. Explicit ai.dlogs/ai.resume
        # invocations still report the underlying metadata failure.
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
        # One displayed name can refer to several dialogs. Keep every
        # identity in its description; rank the name by the newest
        # matching dialog instead of silently selecting that dialog.
        updated[name] = max(
            updated.get(name, 0),
            row.get('updated_at', 0),
        )

    sort_by: str = (environment or {}).get(
        'AI_RESUME_COMPLETION_SORT', 'last-update-time',
    )
    names: list[str] = sorted(
        groups,
        key=lambda name: (
            name.casefold(),
            name,
        ),
    )
    if sort_by != 'name':
        # Stable sorting preserves alphabetical order for equal
        # times.
        names.sort(key=lambda name: updated[name], reverse=True)

    result: list[RichCompletion] = []
    quote: str = command.opening_quote or "'"
    name: str
    for name in names:
        details: list[str] = groups[name]
        literal_injection: bool = '$' in name or name.startswith('~')
        closing_quote_remains: bool = (
            bool(command.closing_quote)
            and not command.is_after_closing_quote
        )
        if literal_injection and closing_quote_remains:
            # @('literal') suppresses Xonsh's $ and ~ expansion. We
            # cannot insert that expression inside an existing quote
            # pair: the replacement span does not own the suffix
            # quote.
            continue

        escaped: list[str] = []
        char: str
        for char in name:
            if char == quote:
                escaped.append('\\' + char)
            else:
                # JSON quotes each character and escapes controls and
                # backslashes. Remove only its outer double quotes;
                # the matching Xonsh quote is escaped by the branch
                # above. The stored dialog name itself stays intact.
                escaped.append(
                    json.dumps(char, ensure_ascii=True)[1:-1],
                )

        closing: str = quote
        if closing_quote_remains:
            closing = ''

        value: str = quote + ''.join(escaped) + closing
        if literal_injection:
            value = '@(' + repr(name) + ')'

        result.append(RichCompletion(
            value,
            # Replace the typed opening quote too, but not unrelated
            # arguments. We supply the closing quote ourselves; an
            # extra Xonsh quote would alter the resulting argument.
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


def _install_completion_order(xsh: XonshSession) -> None:
    '''
    Preserve dialog recency through Xonsh's final candidate sorting.

    - Wrap `Completer.complete_from_context()`, not every completer.
    - Clear `_resume_order` before calling Xonsh's original method.
    - Reorder only when complete_resume set ranks for every result.
      Mixed results from unrelated completers keep Xonsh's ordering.
    - Restore the previous method on unload only if we still own it.

    Registering our completer first is insufficient: Xonsh sorts the
    combined result afterward. The wrapper restores only our ranks;
    it does not change generation, replacement spans or other APIs.

    '''
    current: CompletionMethod = Completer.complete_from_context
    if current is not xsh.ctx.get('_aiskillz_sort_wrapper'):
        xsh.ctx['_aiskillz_sort_original'] = current

    original: CompletionMethod = cast(
        CompletionMethod,
        xsh.ctx['_aiskillz_sort_original'],
    )

    def ordered_completions(
        self: Completer,
        completion_context: CompletionContext|None,
        old_completer_args: tuple|None = None,
    ) -> CompletionBatch:
        '''
        Apply the invocation's dialog ranks after Xonsh completes.

        The finally clause restores ContextVar state even if another
        completer raises or completion recursively invokes itself.

        '''
        token: Token[dict[str, int]|None] = _resume_order.set(None)
        try:
            results: tuple[str|RichCompletion, ...]
            prefix: int
            results, prefix = original(
                self,
                completion_context,
                old_completer_args,
            )
            order: dict[str, int]|None = _resume_order.get()
            item: str|RichCompletion
            if order and all(str(item) in order for item in results):
                results = tuple(sorted(
                    results,
                    key=lambda item: order[str(item)],
                ))

            return results, prefix

        finally:
            _resume_order.reset(token)

    Completer.complete_from_context = ordered_completions
    xsh.ctx['_aiskillz_sort_wrapper'] = ordered_completions


def register_resume_completer(xsh: XonshSession) -> None:
    '''
    Register before fallback command/path completers in Xonsh.

    - Both `_load_xontrib_()` and `aliases.xsh` call this entry
      point.
    - Retain the first prior binding while our registration owns it.
    - Remember a subprocess alias's argv for prompt-toolkit
      expansion.
    - Do not assume an initialized shell when a library imports us.

    '''
    registry: dict[str, object]|None = getattr(
        xsh, 'completers', None,
    )
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
    alias: object = xsh.aliases.get('ai.resume')
    argv: list[str]|None = None
    if isinstance(alias, list):
        argv = list(alias)
    xsh.ctx['_aiskillz_completer_argv'] = argv

    remaining: dict[str, object] = dict(registry)
    remaining.pop(key, None)
    registry.clear()
    registry[key] = complete_resume
    registry.update(remaining)


def unregister_resume_completer(xsh: XonshSession) -> None:
    '''
    Release owned hooks while preserving user replacements.

    - Restore the original sorting method only while our wrapper owns
      it.
    - Restore the prior named completer, or remove our new
      registration.
    - Release saved context entries so later loads start a fresh
      lifetime.

    '''
    registry: dict[str, object]|None = getattr(
        xsh, 'completers', None,
    )
    wrapper: object = xsh.ctx.pop('_aiskillz_sort_wrapper', None)
    original: object = xsh.ctx.pop('_aiskillz_sort_original', None)
    if (
        wrapper is not None
        and Completer.complete_from_context is wrapper
    ):
        Completer.complete_from_context = cast(
            CompletionMethod, original,
        )

    command: object = xsh.ctx.pop(
        '_aiskillz_completer_command', None,
    )
    previous: object = xsh.ctx.pop(
        '_aiskillz_completer_previous', None,
    )
    xsh.ctx.pop('_aiskillz_completer_argv', None)
    if (
        registry is not None
        and registry.get('aiskillz_resume') is command
    ):
        if previous is None:
            registry.pop('aiskillz_resume', None)
        else:
            registry['aiskillz_resume'] = previous
