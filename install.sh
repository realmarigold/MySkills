#!/usr/bin/env bash
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

function print_warning() {
  echo -e "${YELLOW}[WARNING]${NC} $1"
}

function print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

if [[ "$1" == "--uninstall" || "$1" == "-u" ]]; then
  print_info "Uninstalling Antigravity plugin '${PLUGIN_NAME}'..."
  if [ -L "${TARGET_DIR}" ]; then
    rm "${TARGET_DIR}"
    print_success "Symlink removed from ${TARGET_DIR}."
  elif [ -d "${TARGET_DIR}" ]; then
    print_warning "${TARGET_DIR} is a directory (not a symlink). Please manually inspect and remove it if appropriate."
    exit 1
  else
    print_info "Plugin is not installed at ${TARGET_DIR}."
  fi
  print_success "Uninstallation completed!"
  exit 0
fi

print_info "Installing '${PLUGIN_NAME}' as an Antigravity plugin..."

# Ensure target plugin directory parent exists
if [ ! -d "${PLUGINS_DIR}" ]; then
  print_info "Creating plugins directory at ${PLUGINS_DIR}..."
  mkdir -p "${PLUGINS_DIR}"
fi

# Check if existing target exists
if [ -L "${TARGET_DIR}" ]; then
  CURRENT_LINK="$(readlink "${TARGET_DIR}")"
  if [ "${CURRENT_LINK}" == "${SCRIPT_DIR}" ]; then
    print_success "Plugin '${PLUGIN_NAME}' is already linked to ${SCRIPT_DIR}."
    exit 0
  else
    print_warning "Updating existing symlink from ${CURRENT_LINK} to ${SCRIPT_DIR}..."
    rm "${TARGET_DIR}"
  fi
elif [ -d "${TARGET_DIR}" ]; then
  print_error "Target location ${TARGET_DIR} exists as a directory. Cannot overwrite with symlink."
  exit 1
fi

# Create symlink
ln -s "${SCRIPT_DIR}" "${TARGET_DIR}"
print_success "Successfully installed '${PLUGIN_NAME}' plugin!"
print_info "Symlink created: ${TARGET_DIR} -> ${SCRIPT_DIR}"
print_info "Antigravity will now automatically discover skills in this plugin."
