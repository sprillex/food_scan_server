#!/bin/bash
set -e

echo "🚀 Setting up Food Scan Server..."

# Ensure python3-venv is installed (Debian/Ubuntu/DietPi/Mint)
# Note: -y is used here to allow the setup script to proceed 
# without pausing for confirmation, which is standard for automation.
if ! dpkg -s python3-venv >/dev/null 2>&1; then
    echo "📦 Installing python3-venv..."
    sudo apt-get update && sudo apt-get install -y python3-venv
fi

# Create Virtual Environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating virtual environment..."
    python3 -m venv venv
fi

# Install Dependencies
echo "📦 Installing dependencies..."
./venv/bin/pip install -r requirements.txt

# Setup Systemd Service
echo "🔧 Configuring systemd service..."
SERVICE_FILE="foodscan.service"
TARGET_DIR="/etc/systemd/system"

# Ensure the source service file actually exists before proceeding
if [ ! -f "$SERVICE_FILE" ]; then
    echo "❌ Error: $SERVICE_FILE not found in current directory."
    exit 1
fi

# Edit the service file to reflect current directory if needed
# (Assuming the default provided in repo matches standard install path /home/dietpi/foodscan)
# If running from a different path, this updates it to your current location.
CURRENT_DIR=$(pwd)

# We define the default expected path to check against
DEFAULT_PATH="/home/dietpi/foodscan"

if [ "$CURRENT_DIR" != "$DEFAULT_PATH" ]; then
    echo "⚠️  Current directory ($CURRENT_DIR) does not match default ($DEFAULT_PATH)."
    echo "    Updating service file paths..."
    # strict quoting to handle potential spaces in paths, though rare in server setups
    sed -i "s|$DEFAULT_PATH|$CURRENT_DIR|g" "$SERVICE_FILE"
    sed -i "s|User=dietpi|User=$USER|g" "$SERVICE_FILE"
fi

echo "📋 Copying service file to systemd directory..."
sudo cp "$SERVICE_FILE" "$TARGET_DIR/"
sudo systemctl daemon-reload
sudo systemctl enable foodscan
sudo systemctl restart foodscan

echo "✅ Setup complete! Service is running."
sudo systemctl status foodscan --no-pager
