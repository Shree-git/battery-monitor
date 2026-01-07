#!/bin/bash
#
# Battery Monitor Installation Script for macOS
# Installs the battery monitoring daemon with launchd integration
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/.battery_monitor"
BIN_DIR="$HOME/.local/bin"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_NAME="com.battery-monitor.daemon.plist"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║          🔋 Battery Monitor Installation             ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════╝${NC}"
echo

# Check for Python 3
echo -e "${YELLOW}→ Checking Python 3...${NC}"
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo -e "${GREEN}  ✓ Found $PYTHON_VERSION${NC}"
else
    echo -e "${RED}  ✗ Python 3 not found. Please install Python 3.${NC}"
    exit 1
fi

# Create directories
echo -e "${YELLOW}→ Creating directories...${NC}"
mkdir -p "$INSTALL_DIR"
mkdir -p "$BIN_DIR"
mkdir -p "$LAUNCH_AGENTS_DIR"
echo -e "${GREEN}  ✓ Directories created${NC}"

# Copy Python files
echo -e "${YELLOW}→ Installing Python modules...${NC}"
cp "$SCRIPT_DIR/battery_collector.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/battery_database.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/battery_daemon.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/battery_cli.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/dashboard.html" "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/battery_daemon.py"
chmod +x "$INSTALL_DIR/battery_cli.py"
echo -e "${GREEN}  ✓ Python modules installed${NC}"

# Create the 'battery' command wrapper
echo -e "${YELLOW}→ Creating 'battery' command...${NC}"
cat > "$BIN_DIR/battery" << 'EOF'
#!/bin/bash
BATTERY_DIR="$HOME/.battery_monitor"
cd "$BATTERY_DIR"
python3 "$BATTERY_DIR/battery_cli.py" "$@"
EOF
chmod +x "$BIN_DIR/battery"
echo -e "${GREEN}  ✓ Command 'battery' created${NC}"

# Create the 'battery-daemon' command wrapper
cat > "$BIN_DIR/battery-daemon" << 'EOF'
#!/bin/bash
BATTERY_DIR="$HOME/.battery_monitor"
cd "$BATTERY_DIR"
python3 "$BATTERY_DIR/battery_daemon.py" "$@"
EOF
chmod +x "$BIN_DIR/battery-daemon"
echo -e "${GREEN}  ✓ Command 'battery-daemon' created${NC}"

# Create launchd plist
echo -e "${YELLOW}→ Creating launchd service...${NC}"
cat > "$LAUNCH_AGENTS_DIR/$PLIST_NAME" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.battery-monitor.daemon</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>${INSTALL_DIR}/battery_daemon.py</string>
        <string>start</string>
        <string>-f</string>
        <string>-i</string>
        <string>60</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${INSTALL_DIR}</string>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>${INSTALL_DIR}/stdout.log</string>
    
    <key>StandardErrorPath</key>
    <string>${INSTALL_DIR}/stderr.log</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
</dict>
</plist>
EOF
echo -e "${GREEN}  ✓ LaunchAgent plist created${NC}"

# Add bin directory to PATH if needed
if [[ ":$PATH:" != *":$BIN_DIR:"* ]]; then
    echo -e "${YELLOW}→ Updating PATH...${NC}"
    
    # Detect shell and update appropriate config
    SHELL_RC=""
    if [[ "$SHELL" == *"zsh"* ]]; then
        SHELL_RC="$HOME/.zshrc"
    elif [[ "$SHELL" == *"bash"* ]]; then
        SHELL_RC="$HOME/.bashrc"
    fi
    
    if [[ -n "$SHELL_RC" ]]; then
        if ! grep -q "battery_monitor" "$SHELL_RC" 2>/dev/null; then
            echo "" >> "$SHELL_RC"
            echo "# Battery Monitor" >> "$SHELL_RC"
            echo "export PATH=\"\$HOME/.local/bin:\$PATH\"" >> "$SHELL_RC"
            echo -e "${GREEN}  ✓ Updated $SHELL_RC${NC}"
        fi
    fi
fi

# Start the service
echo -e "${YELLOW}→ Starting Battery Monitor service...${NC}"
launchctl unload "$LAUNCH_AGENTS_DIR/$PLIST_NAME" 2>/dev/null || true
launchctl load -w "$LAUNCH_AGENTS_DIR/$PLIST_NAME"
echo -e "${GREEN}  ✓ Service started${NC}"

echo
echo -e "${GREEN}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         ✓ Installation Complete!                     ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════╝${NC}"
echo
echo -e "${BLUE}Usage:${NC}"
echo -e "  ${YELLOW}battery${NC}           - Show current battery status"
echo -e "  ${YELLOW}battery stats${NC}     - View historical statistics"
echo -e "  ${YELLOW}battery apps${NC}      - See app battery impact"
echo -e "  ${YELLOW}battery sessions${NC}  - View discharge sessions"
echo -e "  ${YELLOW}battery health${NC}    - Battery health analysis"
echo -e "  ${YELLOW}battery export${NC}    - Export data to JSON"
echo
echo -e "${BLUE}Dashboard:${NC}"
echo -e "  Open ${YELLOW}$INSTALL_DIR/dashboard.html${NC} in a browser"
echo -e "  Upload exported JSON data to visualize"
echo
echo -e "${BLUE}Service Management:${NC}"
echo -e "  ${YELLOW}launchctl stop com.battery-monitor.daemon${NC}   - Stop"
echo -e "  ${YELLOW}launchctl start com.battery-monitor.daemon${NC}  - Start"
echo
echo -e "${BLUE}Data Location:${NC} $INSTALL_DIR"
echo
echo -e "${YELLOW}Note: Run 'source ~/.zshrc' or open a new terminal to use the 'battery' command.${NC}"
