from pathlib import Path
import sys
from xonsh.built_ins import XSH

# Xonsh initialized XSH with --no-rc before loading this fixed file.
# Compile the whole input, including native blocks/continuations.
# Never exec/eval the returned code object or source the input.
XSH.env['XONSH_CACHE_SCRIPTS'] = False
XSH.execer.compile(
    Path(sys.argv[1]).read_text(), mode='exec', glbs={}, locs={},
)
