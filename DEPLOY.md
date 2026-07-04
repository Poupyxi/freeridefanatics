# Déploiement Freeride Fanatics sur VPS Hostinger (hotcut.xyz)

## Prérequis

- VPS Hostinger KVM2 sous Ubuntu 22.04
- Accès SSH root
- DNS : enregistrement A `freeridefanatics.hotcut.xyz` → IP du VPS (chez ton registrar)

---

## 1. Connexion SSH & mise à jour

```bash
ssh root@<IP_VPS>
apt update && apt upgrade -y
```

---

## 2. Installer Docker

```bash
curl -fsSL https://get.docker.com | sh
systemctl enable docker
systemctl start docker
```

---

## 3. Installer nginx & certbot

```bash
apt install -y nginx certbot python3-certbot-nginx
```

---

## 4. Créer le réseau Docker partagé Hotcut

```bash
docker network create hotcut
```

---

## 5. Déposer les fichiers sur le VPS

Depuis ton Mac (dans le dossier freeride) :

```bash
# Créer le dossier sur le VPS
ssh root@<IP_VPS> "mkdir -p /opt/hotcut/freeridefanatics"

# Envoyer le code source (sans les données sensibles)
rsync -av --exclude='PPRIDERS/' --exclude='Equipment/' \
  --exclude='output/' --exclude='flags/' --exclude='*.json' \
  --exclude='__pycache__/' --exclude='.git/' \
  ~/Desktop/freeride/ root@<IP_VPS>:/opt/hotcut/freeridefanatics/

# Envoyer les credentials Google OAuth séparément dans /data
ssh root@<IP_VPS> "mkdir -p /opt/hotcut/freeridefanatics/data"
scp ~/.config/freeridefanatics/google_client_secret.json \
  root@<IP_VPS>:/opt/hotcut/freeridefanatics/data/
```

---

## 6. Build et lancer le container

```bash
cd /opt/hotcut/freeridefanatics
docker compose up -d --build
```

Vérifier que le container tourne :
```bash
docker ps
docker logs freeridefanatics
```

---

## 7. Config nginx

```bash
cp /opt/hotcut/freeridefanatics/nginx-freeride.conf \
   /etc/nginx/sites-available/freeridefanatics
ln -s /etc/nginx/sites-available/freeridefanatics \
      /etc/nginx/sites-enabled/freeridefanatics
nginx -t && systemctl reload nginx
```

---

## 8. SSL avec Certbot

```bash
certbot --nginx -d freeridefanatics.hotcut.xyz
# Certbot modifie automatiquement le fichier nginx pour HTTPS
systemctl reload nginx
```

Renouvellement automatique (déjà actif avec certbot) :
```bash
certbot renew --dry-run   # pour tester
```

---

## 9. Mettre à jour l'app

```bash
# Depuis ton Mac
rsync -av --exclude='PPRIDERS/' --exclude='Equipment/' \
  --exclude='output/' --exclude='flags/' --exclude='*.json' \
  --exclude='__pycache__/' --exclude='.git/' \
  ~/Desktop/freeride/ root@<IP_VPS>:/opt/hotcut/freeridefanatics/

# Sur le VPS
cd /opt/hotcut/freeridefanatics
docker compose up -d --build
```

---

## Structure sur le VPS

```
/opt/hotcut/
  └── freeridefanatics/
        ├── app.py
        ├── generate_cards.py
        ├── generate_equipment_card.py
        ├── Dockerfile
        ├── docker-compose.yml
        ├── requirements.txt
        ├── fonts/
        ├── logos/          ← logos des marques
        ├── PPRIDERS/       ← photos riders (à uploader manuellement)
        ├── Equipment/      ← photos équipements (à uploader manuellement)
        ├── output/         ← cartes générées (créé automatiquement)
        ├── flags/          ← drapeaux (à uploader manuellement)
        └── data/
              └── google_client_secret.json
```

---

## Ajouter un deuxième projet (ex: client2.hotcut.xyz)

```bash
mkdir -p /opt/hotcut/client2
# Copier/adapter les fichiers, changer le port dans docker-compose.yml (ex: 5002)
# Créer un nginx-client2.conf avec server_name client2.hotcut.xyz
# certbot --nginx -d client2.hotcut.xyz
```

---

## Google OAuth — URI de redirection à mettre à jour

Dans la Google Cloud Console, ajouter l'URI autorisée :
```
https://freeridefanatics.hotcut.xyz/api/auth/google/callback
```
