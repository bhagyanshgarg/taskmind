#!/bin/bash
# TaskMind Installer for Ubuntu 18.04+
# Usage: bash install.sh
set -e

APP="TaskMind"
INSTALL_DIR="$HOME/.local/share/taskmind"
CONFIG_DIR="$HOME/.config/taskmind"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "🧠 Installing $APP..."
echo ""

# Check we're on a Debian/Ubuntu system
if ! command -v apt-get &>/dev/null; then
    echo "Error: apt-get not found. This installer supports Ubuntu/Debian only."
    exit 1
fi

# Install system dependencies
echo "[1/6] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv \
    xdotool xprintidle libnotify-bin 2>/dev/null || {
    echo "Warning: Some packages may not be available. Continuing..."
}

# Create directories
echo "[2/6] Creating directories..."
mkdir -p "$INSTALL_DIR/logs"
mkdir -p "$INSTALL_DIR/recordings"
mkdir -p "$CONFIG_DIR"

# Create virtual environment
echo "[3/6] Setting up Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
source "$INSTALL_DIR/venv/bin/activate"

# Install Python package
echo "[4/6] Installing TaskMind Python package..."
pip install --quiet --upgrade pip
pip install --quiet "$SCRIPT_DIR"

# Copy config files if they don't exist
echo "[5/6] Setting up configuration..."
if [ ! -f "$CONFIG_DIR/config.yaml" ]; then
    cp "$SCRIPT_DIR/configs/config.default.yaml" "$CONFIG_DIR/config.yaml"
    echo "  Created $CONFIG_DIR/config.yaml"
fi
if [ ! -f "$CONFIG_DIR/projects.yaml" ]; then
    cp "$SCRIPT_DIR/configs/projects.example.yaml" "$CONFIG_DIR/projects.yaml"
    echo "  Created $CONFIG_DIR/projects.yaml"
fi

# Install systemd user service
echo "[6/6] Installing systemd service..."
mkdir -p "$HOME/.config/systemd/user"
cat > "$HOME/.config/systemd/user/taskmind.service" << EOF
[Unit]
Description=TaskMind Activity Tracker
After=graphical-session.target

[Service]
Type=simple
ExecStart=$INSTALL_DIR/venv/bin/python -m taskmind.daemon
Restart=on-failure
RestartSec=5
Environment=DISPLAY=:0
Environment=XAUTHORITY=$HOME/.Xauthority

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable taskmind 2>/dev/null || true

# Create symlink for CLI
mkdir -p "$HOME/.local/bin"
ln -sf "$INSTALL_DIR/venv/bin/taskmind" "$HOME/.local/bin/taskmind"

echo ""
echo "✅ $APP installed successfully!"
echo ""
echo "Quick Start:"
echo "  taskmind start       - Start tracking"
echo "  taskmind status      - Check status"
echo "  taskmind today       - See today's activity"
echo "  taskmind timesheet   - Generate timesheet"
echo "  taskmind stop        - Stop tracking"
echo ""
echo "Config: $CONFIG_DIR/config.yaml"
echo "Projects: $CONFIG_DIR/projects.yaml"
echo ""
echo "To start automatically on login:"
echo "  systemctl --user start taskmind"
echo ""
echo "Make sure ~/.local/bin is in your PATH:"
echo "  export PATH=\"\$HOME/.local/bin:\$PATH\""
