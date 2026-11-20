FROM srtp:20261117
ENV SRTP_ENV_FILE=/app/.runtime/server.env
COPY framework/backend/app/core/config.py /app/framework/backend/app/core/config.py
COPY framework/backend/app/api/settings.py /app/framework/backend/app/api/settings.py
COPY deploy/ecs/verify_ai.py /app/deploy/ecs/verify_ai.py
