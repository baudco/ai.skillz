# Copyright (C) 2025-2026 baudco — Tyler Goodlet and contributors.
# Licensed under the GNU Affero General Public License v3.0.
# See LICENSE and LICENSING.md for terms and commercial licensing.


'''
Protect package dependency boundaries and source CLI entrypoints.

'''

import ast
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest

import aiskillz


@pytest.mark.parametrize('layer', ['git', 'wkt', 'dialogs'])
def test_imports_follow_layer_direction(layer: str) -> None:
    '''
    The former modules mixed CLI dispatch, Git and harness readers.

    Resolve every static import in each layer, including function
    bodies, and reject imports of a higher layer or CLI. This keeps
    replacing Git discovery independent of harness adapters, and
    prevents shell presentation from becoming a library dependency.

    '''
    root: Path = Path(aiskillz.__file__).parent
    allowed: set[str] = {
        'git': {'git'},
        'wkt': {'git', 'wkt'},
        'dialogs': {'git', 'wkt', 'dialogs'},
    }[layer]
    source: Path
    for source in (root / layer).glob('*.py'):
        module: ast.Module = ast.parse(source.read_text())
        node: ast.AST
        for node in ast.walk(module):
            imports: list[str] = []
            if isinstance(node, ast.ImportFrom):
                name: str = '.' * node.level + (node.module or '')
                resolved: str = importlib.util.resolve_name(
                    name, 'aiskillz.' + layer,
                )
                imports.append(resolved)
                if resolved == 'aiskillz':
                    alias: ast.alias
                    imports.extend(
                        resolved + '.' + alias.name
                        for alias in node.names
                    )
            elif isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            imported: str
            for imported in imports:
                if imported.startswith('aiskillz.'):
                    assert imported.split('.')[1] in allowed, (
                        source, imported,
                    )


def test_source_and_module_cli_outside_checkout(
    tmp_path: Path,
) -> None:
    '''
    Moving main() into cli.py must preserve skill source execution.

    Launch the source script from an unrelated directory with no
    PYTHONPATH, then invoke python -m aiskillz from the checkout.
    Both must expose the same index options without reading user logs
    or needing an editable installation of these new subpackages.

    '''
    root: Path = Path(aiskillz.__file__).parent.parent
    import os

    env: dict[str, str] = dict(os.environ)
    env.pop('PYTHONPATH', None)
    source: subprocess.CompletedProcess = subprocess.run(
        [sys.executable, str(root / 'aiskillz/cli.py'),
         'index', '--help'],
        cwd=tmp_path, env=env, capture_output=True, text=True,
        check=True,
    )
    package: subprocess.CompletedProcess = subprocess.run(
        [sys.executable, '-m', 'aiskillz', 'index', '--help'],
        cwd=root, env=env,
        capture_output=True, text=True, check=True,
    )
    assert source.stdout == package.stdout
    assert '--record' in source.stdout
    assert '--apply' in source.stdout
