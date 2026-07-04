#!/bin/bash
# ═══════════════════════════════════════════════════════════
#  Freeride Fanatics — Script de déploiement VPS Hostinger
#  hotcut.xyz  •  freeridefanatics.hotcut.xyz
# ═══════════════════════════════════════════════════════════
set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

APP_DIR="/opt/hotcut/freeridefanatics"
DOMAIN="freeridefanatics.hotcut.xyz"

# ── 1. Mise à jour système ─────────────────────────────────
log "Mise à jour système..."
apt-get update -qq && apt-get upgrade -y -qq

# ── 2. Docker ─────────────────────────────────────────────
if ! command -v docker &> /dev/null; then
  log "Installation Docker..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable docker
  systemctl start docker
else
  log "Docker déjà installé ✓"
fi

# ── 3. nginx + certbot ────────────────────────────────────
if ! command -v nginx &> /dev/null; then
  log "Installation nginx + certbot..."
  apt-get install -y -qq nginx certbot python3-certbot-nginx
else
  log "nginx déjà installé ✓"
fi

# ── 4. Réseau Docker partagé ──────────────────────────────
if ! docker network ls | grep -q hotcut; then
  log "Création réseau Docker 'hotcut'..."
  docker network create hotcut
else
  log "Réseau 'hotcut' déjà existant ✓"
fi

# ── 5. Dossier app ────────────────────────────────────────
log "Création des dossiers..."
mkdir -p $APP_DIR/{PPRIDERS,Equipment,output,flags,logos,data,fonts}

# ── 6. Cloner depuis GitHub ───────────────────────────────
if [ ! -f "$APP_DIR/app.py" ]; then
  log "Clonage du repo GitHub..."
  apt-get install -y -qq git
  git clone https://github.com/Poupyxi/freeridefanatics.git /tmp/freeride_tmp
  cp -r /tmp/freeride_tmp/. $APP_DIR/
  rm -rf /tmp/freeride_tmp
else
  log "Code déjà présent, mise à jour..."
  cd $APP_DIR && git pull origin main 2>/dev/null || warn "git pull ignoré (pas de repo git local)"
fi

# ── 7. Config nginx ───────────────────────────────────────
log "Configuration nginx..."
cat > /etc/nginx/sites-available/freeridefanatics << 'NGINX'
server {
    listen 80;
    server_name freeridefanatics.hotcut.xyz;

    client_max_body_size 20M;

    location / {
        proxy_pass         http://127.0.0.1:5001;
        proxy_http_version 1.1;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
        proxy_read_timeout 120s;
    }
}
NGINX

ln -sf /etc/nginx/sites-available/freeridefanatics \
        /etc/nginx/sites-enabled/freeridefanatics
nginx -t && systemctl reload nginx

# ── 8. Build Docker ───────────────────────────────────────
log "Build du container Docker..."
cd $APP_DIR
docker compose down 2>/dev/null || true
docker compose up -d --build

# ── 9. SSL Certbot ────────────────────────────────────────
log "Génération certificat SSL..."
warn "Assure-toi que freeridefanatics.hotcut.xyz pointe bien vers ce serveur !"
read -p "DNS configuré ? (o/n) : " dns_ok
if [ "$dns_ok" = "o" ]; then
  certbot --nginx -d $DOMAIN --non-interactive --agree-tos -m admin@hotcut.xyz
  systemctl reload nginx
  log "SSL activé ✓"
else
  warn "SSL ignoré — relance : certbot --nginx -d $DOMAIN"
fi

# ── 10. Résumé ────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════"
log "Déploiement terminé !"
echo "  Container : $(docker ps --filter name=freeridefanatics --format '{{.Status}}')"
echo "  URL       : http://$DOMAIN (ou https si SSL ok)"
echo ""
echo "  Prochaines étapes :"
echo "  1. Uploader tes données : scp -r ~/Desktop/freeride/PPRIDERS root@VPS:$APP_DIR/"
echo "  2. Uploader logos       : scp -r ~/Desktop/freeride/logos root@VPS:$APP_DIR/"
echo "  3. Copier google secret : scp ~/.config/freeridefanatics/google_client_secret.json root@VPS:$APP_DIR/data/"
echo "═══════════════════════════════════════════════"
