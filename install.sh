#!/usr/bin/env bash
# Note: Antigravity Language Server (Go os.ReadDir) requires a real directory (entry.IsDir() == true)
# and ignores top-level symlinks in ~/.gemini/config/plugins/. This script copies the clean plugin bundle.
set -e

PLUGIN_NAME="myskills"
PLUGINS_DIR="${HOME}/.gemini/config/plugins"
TARGET_DIR="${PLUGINS_DIR}/${PLUGIN_NAME}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Color definitions
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

function print_success() {
  echo -e "${GREEN}[SUCCESS]${NC} $1"
}

function print_info() {
  echo -e "[INFO] $1"
}

function enable_plugin_in_antigravity() {
  if [ -n "${ANTIGRAVITY_CSRF_TOKEN:-}" ]; then
    local addr="${ANTIGRAVITY_LS_ADDRESS:-localhost:5387}"
    curl -sS -X POST \
      "http://${addr}/exa.language_server_pb.LanguageServerService/JetboxWriteState" \
      -H "Content-Type: application/json" \
      -H "x-codeium-csrf-token: ${ANTIGRAVITY_CSRF_TOKEN}" \
      -d "{\"userConfig\":{\"plugins\":{\"${PLUGIN_NAME}\":{\"enabled\":true}}}}" >/dev/null 2>&1 || true
  fi
}

function remove_target() {
  if [ -L "${TARGET_DIR}" ]; then
    rm -f "${TARGET_DIR}"
  elif [ -d "${TARGET_DIR}" ]; then
    rm -rf "${TARGET_DIR}"
  fi
}

if [[ "$1" == "--uninstall" || "$1" == "-u" ]]; then
  print_info "Uninstalling Antigravity plugin '${PLUGIN_NAME}'..."
  enable_plugin_in_antigravity
  if [ -L "${TARGET_DIR}" ] || [ -d "${TARGET_DIR}" ]; then
    remove_target
    print_success "Removed plugin from ${TARGET_DIR}."
  else
    print_info "Plugin is not installed at ${TARGET_DIR}."
  fi
  print_success "Uninstallation completed!"
  exit 0
fi

print_info "Installing '${PLUGIN_NAME}' as an Antigravity 2.0 plugin..."

mkdir -p "${PLUGINS_DIR}"

if [ -L "${TARGET_DIR}" ] || [ -d "${TARGET_DIR}" ]; then
  print_info "Updating existing plugin installation at ${TARGET_DIR}..."
  remove_target
fi

mkdir -p "${TARGET_DIR}"
cp "${SCRIPT_DIR}/plugin.json" "${TARGET_DIR}/"
[ -f "${SCRIPT_DIR}/README.md" ] && cp "${SCRIPT_DIR}/README.md" "${TARGET_DIR}/"
[ -d "${SCRIPT_DIR}/assets" ] && cp -R "${SCRIPT_DIR}/assets" "${TARGET_DIR}/assets"
[ -d "${SCRIPT_DIR}/skills" ] && cp -R "${SCRIPT_DIR}/skills" "${TARGET_DIR}/skills"

enable_plugin_in_antigravity
print_success "Successfully installed '${PLUGIN_NAME}' plugin to ${TARGET_DIR}!"
print_info "Manage plugin at: customization://${PLUGIN_NAME}"
