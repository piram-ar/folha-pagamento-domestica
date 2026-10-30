#!/bin/sh
# Backup consistente do SQLite (seguro com a aplicação rodando).
# Agende no Pi com:  crontab -e  ->  0 3 * * * /mnt/dietpi_userdata/folha-domestica/scripts/backup.sh
set -e
DIR="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="$DIR/backups"
mkdir -p "$DESTINO"
ARQ="database-$(date +%Y%m%d-%H%M).db"
docker exec folha-backend python -c "import sqlite3; s=sqlite3.connect('/data/database.db'); d=sqlite3.connect('/data/$ARQ'); s.backup(d); d.close()"
mv "$DIR/data/$ARQ" "$DESTINO/$ARQ"
# mantém os 30 backups mais recentes
ls -1t "$DESTINO"/database-*.db | tail -n +31 | xargs -r rm --
echo "Backup salvo em $DESTINO/$ARQ"
