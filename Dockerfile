FROM python:3.12-slim

# Dépendances système (Pillow + fonts)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libfreetype6-dev \
    libjpeg-dev \
    libpng-dev \
    libwebp-dev \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Dépendances Python d'abord (cache Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn

# Polices attendues par le code
RUN mkdir -p /app/fonts

# Code source
COPY app.py generate_cards.py generate_equipment_card.py RIDERS.py config.py ./

# Dossiers statiques (fonts, logos embarqués)
COPY AntonSC-Regular.ttf BebasNeue-Regular.ttf ./fonts/
COPY logos/ ./logos/
COPY background.png ./background.png
COPY equipment_card_bg.png ./equipment_card_bg.png

# Données montées en volume au runtime — pas dans l'image :
#   /app/PPRIDERS   → photos riders
#   /app/Equipment  → photos équipements
#   /app/output     → cartes générées
#   /app/flags      → drapeaux
#   /data           → credentials Google (.json, flask_secret.key)

EXPOSE 5000

ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
