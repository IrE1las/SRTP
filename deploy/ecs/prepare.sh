#!/bin/sh
set -eu
cd /opt/srtp
cp deploy/ecs/dockerignore .dockerignore
mkdir -p .runtime
chmod 700 .runtime
if [ ! -f .runtime/server.env ]; then
    docker run --rm -v /opt/srtp/.runtime:/data python:3.12-slim python -c '
import os,secrets
from pathlib import Path
os.umask(0o077)
p=Path("/data")
password=secrets.token_urlsafe(24)
(p/"server.env").write_text("DATABASE_URL=sqlite:////app/.runtime/railway.db\nSECRET_KEY="+secrets.token_urlsafe(64)+"\nDEEPSEEK_API_KEY=\n")
(p/"bootstrap.env").write_text("SRTP_INITIAL_ADMIN_PASSWORD="+password+"\n")
(p/"admin-credentials.txt").write_text("SRTP administrator\nUsername: admin\nPassword: "+password+"\n")
'
fi
docker build -f deploy/ecs/Dockerfile -t srtp:20261117 .
chown -R 10001:10001 .runtime
if [ ! -f .runtime/ecs-initialized ]; then
    docker run --rm --user 10001:10001 --env-file .runtime/server.env --env-file .runtime/bootstrap.env \
        -v /opt/srtp/.runtime:/app/.runtime srtp:20261117 python /app/deploy/ecs/initialize.py
fi
docker run -d --name srtp --restart unless-stopped --user 10001:10001 \
    --cap-drop ALL --security-opt no-new-privileges --memory 1g --pids-limit 256 \
    --log-opt max-size=10m --log-opt max-file=3 \
    --env-file .runtime/server.env -v /opt/srtp/.runtime:/app/.runtime \
    -p 127.0.0.1:18000:8000 srtp:20261117
echo 'Backend started on loopback port 18000; public traffic has not been switched.'
