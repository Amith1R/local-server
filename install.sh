#!/bin/bash
# ═══════════════════════════════════════════
#  Seedbox Web Dashboard — Installer
#  Run once on the laptop as user amit
# ═══════════════════════════════════════════
set -e

INSTALL_DIR="$HOME/seedbox-web"
SERVICE_FILE="seedbox-web.service"

echo ""
echo "  🌊 Seedbox Web Dashboard Installer"
echo "  ──────────────────────────────────"
echo ""

# ── 1. Copy files ──────────────────────────
echo "  ▶ Copying files to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR/templates"
cp app.py           "$INSTALL_DIR/"
cp requirements.txt "$INSTALL_DIR/"
cp -r templates/    "$INSTALL_DIR/"
echo "  ✅ Files copied"

# ── 2. Python venv ─────────────────────────
echo "  ▶ Creating Python virtual environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --quiet --upgrade pip
"$INSTALL_DIR/venv/bin/pip" install --quiet -r requirements.txt
echo "  ✅ Virtual environment ready"

# ── 3. Systemd service ─────────────────────
echo "  ▶ Installing systemd service..."
sudo cp "$SERVICE_FILE" /etc/systemd/system/
sudo sed -i "s|/home/amit|$HOME|g" /etc/systemd/system/seedbox-web.service
sudo sed -i "s|User=amit|User=$USER|g" /etc/systemd/system/seedbox-web.service
sudo systemctl daemon-reload
sudo systemctl enable seedbox-web
sudo systemctl restart seedbox-web
echo "  ✅ Service installed and started"

# ── 4. UFW firewall ────────────────────────
if command -v ufw &>/dev/null; then
    echo "  ▶ Opening port 5000 in firewall..."
    sudo ufw allow 5000/tcp &>/dev/null
    echo "  ✅ Port 5000 allowed"
fi

# ── Done ───────────────────────────────────
LOCAL_IP=$(hostname -I | awk '{print $1}')
echo ""
echo "  ╔═══════════════════════════════════════════╗"
echo "  ║   ✅  Dashboard installed successfully!   ║"
echo "  ╠═══════════════════════════════════════════╣"
echo "  ║                                           ║"
echo "  ║  Open in browser:                         ║"
echo "  ║  → http://$LOCAL_IP:5000                  ║"
echo "  ║                                           ║"
echo "  ║  Check status:                            ║"
echo "  ║  → systemctl status seedbox-web           ║"
echo "  ║                                           ║"
echo "  ║  View logs:                               ║"
echo "  ║  → journalctl -u seedbox-web -f           ║"
echo "  ║                                           ║"
echo "  ╚═══════════════════════════════════════════╝"
echo ""
