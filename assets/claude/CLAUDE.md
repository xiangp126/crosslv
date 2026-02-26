# Project Notes

- `jk` is an alias for `jmake` (located at `$HOME/.usr/bin/jmake`). Use `jmake` directly in Bash since shell aliases aren't available.
- When running builds in other directories, prefix with `cd /path/to/dir &&`.
- `code` is a bash function defined in `$HOME/Templates/code-function.sh`. It's a VS Code / Cursor remote CLI wrapper. Before using `code`, source the function first: `source $HOME/Templates/code-function.sh && code <args>`.
