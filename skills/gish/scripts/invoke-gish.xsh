#!/usr/bin/env xonsh

import sys


xontrib load gish

try:
    gish = aliases['gish']
except KeyError:
    raise RuntimeError(
        'the selected xonsh loaded no `gish` alias'
    ) from None

args = sys.argv[5:]
if args == ['--adapter-check']:
    print(f'gish xontrib ready via {sys.executable}')
else:
    gish(args, '')
