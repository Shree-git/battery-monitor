#!/bin/bash
#
# Battery Monitor Uninstallation Script
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m'

INSTALL_DIR="$HOME/.battery_monitor"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.battery-monitor.daemon.plist"

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🔋 Battery Monitor Uninstallation           ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo

read -p "This will remove Battery Monitor and all data. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo -e "${YELLOW}→ Stopping service...${NC}"
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
echo -e "${GREEN}  ✓ Service stopped${NC}"

echo -e "${YELLOW}→ Removing launchd plist...${NC}"
rm -f "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
echo -e "${GREEN}  ✓ Plist removed${NC}"

echo -e "${YELLOW}→ Removing commands...${NC}"
rm -f "$BIN_DIR/battery"
rm -f "$BIN_DIR/battery-daemon"
echo -e "${GREEN}  ✓ Commands removed${NC}"

echo -e "${YELLOW}→ Removing data directory...${NC}"
rm -rf "$INSTALL_DIR"
echo -e "${GREEN}  ✓ Data directory removed${NC}"

echo
echo -e "${GREEN}✓ Battery Monitor has been uninstalled.${NC}"
echo
echo -e "${YELLOW}Note: You may want to remove the PATH entry from your shell config.${NC}"
