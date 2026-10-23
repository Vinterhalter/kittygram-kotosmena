#!/usr/bin/env bash
set -euo pipefail
# Run inside a fresh Ubuntu VM. The first argument is the mounted source directory.
SOURCE_DIR="${1:?Pass the path to the Kittygram source directory}"
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv postgresql nginx git curl docker.io docker-compose-v2
systemctl enable --now postgresql docker nginx
id kittygram >/dev/null 2>&1 || useradd --system --create-home --home-dir /opt/kittygram --shell /usr/sbin/nologin kittygram
install -d -o kittygram -g www-data /opt/kittygram
# The source archive contains no production database or secret environment file.
tar -C "$SOURCE_DIR" --exclude=.git --exclude=.env --exclude=__pycache__ --exclude='*.pyc' --exclude='*.sqlite3' --exclude=backend/media --exclude=backend/private_media --exclude=backend/staticfiles -cf - . | tar -C /opt/kittygram -xf -
chown -R kittygram:www-data /opt/kittygram
sudo -u kittygram python3 -m venv /opt/kittygram/.venv
sudo -u kittygram /opt/kittygram/.venv/bin/pip install -r /opt/kittygram/requirements.txt
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname='kittygram'" | grep -q 1; then
    sudo -u postgres createuser kittygram
fi
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='kittygram'" | grep -q 1; then
    sudo -u postgres createdb -O kittygram kittygram
fi
if [ ! -e /opt/kittygram/.env ]; then
    python3 - <<'PY'
from pathlib import Path
import secrets, subprocess
password=secrets.token_hex(32)
subprocess.run(['sudo','-u','postgres','psql','-v','ON_ERROR_STOP=1','-c',f"ALTER USER kittygram PASSWORD '{password}'"],check=True,capture_output=True)
Path('/opt/kittygram/.env').write_text('SECRET_KEY='+secrets.token_urlsafe(50)+'\nDEBUG=False\nALLOWED_HOSTS=127.0.0.1,localhost\nHTTPS=False\nPOSTGRES_HOST=127.0.0.1\nPOSTGRES_DB=kittygram\nPOSTGRES_USER=kittygram\nPOSTGRES_PASSWORD='+password+'\nPOSTGRES_PORT=5432\n')
PY
    chown kittygram:www-data /opt/kittygram/.env
    chmod 640 /opt/kittygram/.env
fi
install -d -o kittygram -g www-data -m 700 /opt/kittygram/backend/private_media
install -d -o kittygram -g www-data -m 755 /opt/kittygram/backend/media /opt/kittygram/backend/staticfiles
sudo -u kittygram /opt/kittygram/.venv/bin/python /opt/kittygram/backend/manage.py migrate --noinput
sudo -u kittygram /opt/kittygram/.venv/bin/python /opt/kittygram/backend/manage.py collectstatic --noinput
install -m 644 /opt/kittygram/infra/kittygram.service /etc/systemd/system/kittygram.service
sed 's/server_name example.org;/server_name localhost 127.0.0.1;/' /opt/kittygram/infra/nginx-server.conf > /etc/nginx/sites-available/kittygram
ln -sf /etc/nginx/sites-available/kittygram /etc/nginx/sites-enabled/kittygram
rm -f /etc/nginx/sites-enabled/default
systemctl daemon-reload
systemctl enable --now kittygram
nginx -t
systemctl reload nginx
curl --fail --retry 10 --retry-delay 2 --retry-all-errors http://127.0.0.1/api/docs/ -o /dev/null
printf 'Kittygram local Linux server is ready.\n'
