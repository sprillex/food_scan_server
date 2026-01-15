#!/bin/bash
set -e

echo "🚀 Setting up Food Scan Server..."

# Ensure python3-venv is installed (Debian/Ubuntu/DietPi)
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

# --- MIGRATION: Handle rename from hahealth ---
if [ -f "hahealth.service" ] && [ ! -f "foodscan.service" ]; then
    echo "⚠️  Found old service file 'hahealth.service'. Renaming to 'foodscan.service'..."
    mv hahealth.service foodscan.service
fi

if systemctl is-active --quiet hahealth || systemctl is-enabled --quiet hahealth; then
    echo "⚠️  Stopping and disabling old 'hahealth' service..."
    sudo systemctl stop hahealth || true
    sudo systemctl disable hahealth || true
    if [ -f "/etc/systemd/system/hahealth.service" ]; then
        echo "🗑️  Removing old hahealth service file from system..."
        sudo rm /etc/systemd/system/hahealth.service
        sudo systemctl daemon-reload
    fi
fi
# ----------------------------------------------

# Setup Systemd Service
echo "🔧 Configuring systemd service..."
SERVICE_FILE="foodscan.service"
TARGET_DIR="/etc/systemd/system"

# Edit the service file to reflect current directory if needed
# (Assuming the default provided in repo matches standard install path /home/dietpi/foodscan)
# If running from a different path, you might want to update it.
CURRENT_DIR=$(pwd)
if [ "$CURRENT_DIR" != "/home/dietpi/foodscan" ]; then
    echo "⚠️  Current directory ($CURRENT_DIR) does not match default (/home/dietpi/foodscan)."
    echo "    Updating service file paths..."
    sed -i "s|/home/dietpi/foodscan|$CURRENT_DIR|g" $SERVICE_FILE
    sed -i "s|User=dietpi|User=$USER|g" $SERVICE_FILE
fi

sudo cp $SERVICE_FILE $TARGET_DIR/
sudo systemctl daemon-reload
sudo systemctl enable foodscan
sudo systemctl restart foodscan

echo "✅ Setup complete! Service is running."
sudo systemctl status foodscan --no-pager
