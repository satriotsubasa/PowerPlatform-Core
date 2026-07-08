#!/usr/bin/env bash
# Check (and optionally install) the PowerPlatform-Core prerequisite toolchain.
#
# The skills are code-first, so the live path needs a small local toolchain:
#   - Python 3.10+          (required - runs the helper scripts)
#   - .NET 8 SDK            (required - builds/runs the DataverseOps tool + plug-ins)
#   - Power Platform CLI    (required - auth, solution, and deployment operations)
#   - Node.js 18+           (optional - only for PCF controls and Code Apps)
#
# Usage:
#   ./bootstrap.sh            # check only, print how to fix each gap
#   ./bootstrap.sh --install  # check, then try to install anything missing safely
#
# With --install it installs what it can do safely: 'pac' as a .NET global tool, and
# the rest via Homebrew (macOS) or apt (Debian/Ubuntu) when that manager is present.
set -euo pipefail

INSTALL=0
if [[ "${1:-}" == "--install" ]]; then INSTALL=1; fi

# --- terminal colors (no-op when not a tty) ----------------------------------
if [[ -t 1 ]]; then
  C_CYAN=$'\033[36m'; C_GREEN=$'\033[32m'; C_YELLOW=$'\033[33m'; C_RED=$'\033[31m'; C_RESET=$'\033[0m'
else
  C_CYAN=""; C_GREEN=""; C_YELLOW=""; C_RED=""; C_RESET=""
fi

missing_required=()

have() { command -v "$1" >/dev/null 2>&1; }

row() { printf '  %-22s %-6s %s\n' "$1" "$2" "$3"; }

echo
echo "${C_CYAN}PowerPlatform-Core prerequisite check${C_RESET}"
echo "======================================"

# --- Python 3.10+ ------------------------------------------------------------
python_cmd=""
for c in python3 python; do
  if have "$c"; then python_cmd="$c"; break; fi
done
if [[ -n "$python_cmd" ]]; then
  pyver="$("$python_cmd" --version 2>&1 | awk '{print $2}')"
  py_major="${pyver%%.*}"; py_rest="${pyver#*.}"; py_minor="${py_rest%%.*}"
  if [[ "$py_major" -gt 3 || ( "$py_major" -eq 3 && "$py_minor" -ge 10 ) ]]; then
    row "Python 3.10+" "PASS" "$pyver ($python_cmd)"
  else
    row "Python 3.10+" "FAIL" "$pyver is too old"
    missing_required+=("python")
  fi
else
  row "Python 3.10+" "FAIL" "not found"
  missing_required+=("python")
fi

# --- .NET 8 SDK --------------------------------------------------------------
if have dotnet && dotnet --list-sdks 2>/dev/null | grep -q '^8\.'; then
  sdk8="$(dotnet --list-sdks | grep '^8\.' | head -n1)"
  row ".NET 8 SDK" "PASS" "$sdk8"
else
  row ".NET 8 SDK" "FAIL" "no 8.x SDK found"
  missing_required+=("dotnet")
fi

# --- Power Platform CLI ------------------------------------------------------
if have pac; then
  row "Power Platform CLI" "PASS" "$(pac --version 2>&1 | head -n1)"
else
  row "Power Platform CLI" "FAIL" "not found"
  missing_required+=("pac")
fi

# --- Node.js (optional) ------------------------------------------------------
if have node; then
  row "Node.js (optional)" "PASS" "$(node --version 2>&1)"
else
  row "Node.js (optional)" "WARN" "not found (only needed for PCF / Code Apps)"
fi

echo
if [[ ${#missing_required[@]} -eq 0 ]]; then
  echo "${C_GREEN}All required tools are present. You are ready to go.${C_RESET}"
  exit 0
fi

# --- remediation -------------------------------------------------------------
pkg_mgr=""
if have brew; then pkg_mgr="brew"
elif have apt-get; then pkg_mgr="apt"; fi

advise_or_install() {
  case "$1" in
    python)
      if [[ $INSTALL -eq 1 && "$pkg_mgr" == "brew" ]]; then
        echo "${C_YELLOW}-> brew install python@3.12${C_RESET}"; brew install python@3.12
      elif [[ $INSTALL -eq 1 && "$pkg_mgr" == "apt" ]]; then
        echo "${C_YELLOW}-> sudo apt-get install -y python3 python3-pip${C_RESET}"; sudo apt-get install -y python3 python3-pip
      else
        echo "   Install Python 3.10+:  brew install python@3.12  |  sudo apt-get install python3  |  https://www.python.org/downloads/"
      fi
      ;;
    dotnet)
      if [[ $INSTALL -eq 1 && "$pkg_mgr" == "brew" ]]; then
        echo "${C_YELLOW}-> brew install --cask dotnet-sdk${C_RESET}"; brew install --cask dotnet-sdk
      else
        echo "   Install the .NET 8 SDK:  https://dotnet.microsoft.com/download/dotnet/8.0  (brew install --cask dotnet-sdk on macOS)"
      fi
      ;;
    pac)
      # pac installs cleanly as a .NET global tool once the SDK is present.
      if [[ $INSTALL -eq 1 ]] && have dotnet; then
        echo "${C_YELLOW}-> dotnet tool install --global Microsoft.PowerApps.CLI.Tool${C_RESET}"
        dotnet tool install --global Microsoft.PowerApps.CLI.Tool
        echo "   Add \$HOME/.dotnet/tools to PATH (open a new shell) so pac is found."
      else
        echo "   Install pac:  dotnet tool install --global Microsoft.PowerApps.CLI.Tool   (needs the .NET SDK first)"
      fi
      ;;
  esac
}

echo "${C_YELLOW}Missing required tools:${C_RESET}"
for key in "${missing_required[@]}"; do advise_or_install "$key"; done

if [[ $INSTALL -eq 0 ]]; then
  echo
  echo "${C_CYAN}Re-run with --install to attempt the installs above automatically.${C_RESET}"
fi

exit 1
