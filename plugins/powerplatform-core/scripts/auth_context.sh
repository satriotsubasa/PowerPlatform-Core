#!/usr/bin/env sh
# POSIX wrapper for auth_context.py (macOS/Linux counterpart of auth_context.cmd
# and auth_context.ps1). Forwards all arguments to the Python entry point.
#
# Note: the interactive WPF auth dialog is Windows-only. On macOS/Linux this
# wrapper still runs auth_context.py, which resolves the connection from explicit
# arguments / the active PAC profile and uses the device-code sign-in flow.
DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$DIR/auth_context.py" "$@"
