#!/bin/bash
# ─── Trustworthy Science — Droplet Setup Script ─────────────────────────────
# Run this ONCE on a fresh Ubuntu 22.04 DigitalOcean Droplet as root:
#   bash /var/www/trustworthy-science/deploy/setup.sh YOUR_DROPLET_IP
# ─────────────────────────────────────────────────────────────────────────────

set -e

DROPLET_IP="${1:-YOUR_DROPLET_IP}"
REPO_DIR="/var/www/trustworthy-science"

echo "======================================================"
echo " Trustworthy Science — Server Setup"
echo " Droplet IP: $DROPLET_IP"
echo "======================================================"

# ── 1. System packages ──────────────────────────────────────────────────────
echo "[1/7] Installing system packages..."
apt-get update -q
apt-get install -y --no-install-recommends \
    nginx git curl build-essential \
    python3.12 python3.12-venv python3.12-dev \
    nodejs npm \
    certbot python3-certbot-nginx \
    ufw
echo "Done."

# ── 2. Install uv ───────────────────────────────────────────────────────────
echo "[2/7] Installing uv..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
echo "Done."

# ── 3. Python venv + dependencies ───────────────────────────────────────────
echo "[3/7] Setting up Python environment..."
cd "$REPO_DIR"
uv venv .venv
uv pip install --no-dev .
echo "Done."

# ── 4. Build frontend ───────────────────────────────────────────────────────
echo "[4/7] Building frontend..."
cd "$REPO_DIR/frontend"
npm ci
npm run build
cd "$REPO_DIR"
echo "Done."

# ── 5. systemd service ──────────────────────────────────────────────────────
echo "[5/7] Installing systemd service..."
cp "$REPO_DIR/deploy/trustworthy-science.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable trustworthy-science
echo "Done. (Not started yet — create .env first)"

# ── 6. nginx config ─────────────────────────────────────────────────────────
echo "[6/7] Configuring nginx..."
sed "s/YOUR_DROPLET_IP/$DROPLET_IP/g" \
    "$REPO_DIR/deploy/nginx.conf" \
    > /etc/nginx/sites-available/trustworthy-science

# Remove default nginx site
rm -f /etc/nginx/sites-enabled/default
ln -sf /etc/nginx/sites-available/trustworthy-science /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
echo "Done."

# ── 7. Firewall ─────────────────────────────────────────────────────────────
echo "[7/7] Configuring firewall..."
ufw allow OpenSSH
ufw allow 'Nginx Full'
ufw --force enable
echo "Done."

echo ""
echo "======================================================"
echo " Setup complete!"
echo ""
echo " NEXT STEPS:"
echo " 1. Create your .env file:"
echo "    nano $REPO_DIR/.env"
echo "    Add: K2_API_KEY=your_key_here"
echo ""
echo " 2. Start the backend:"
echo "    systemctl start trustworthy-science"
echo "    systemctl status trustworthy-science"
echo ""
echo " 3. Test:"
echo "    curl http://$DROPLET_IP/health"
echo "    Open http://$DROPLET_IP in your browser"
echo "======================================================"
