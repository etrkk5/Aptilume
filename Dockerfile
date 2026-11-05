FROM node:22-bookworm-slim@sha256:4b150b48b4116e2a22f2c39cc27025fbf4f153e2078fd3b14d159fdb5c7279da AS web-build
WORKDIR /build
RUN corepack enable && corepack prepare pnpm@11.25.0 --activate
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml web/.npmrc ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm exec tsc -b && pnpm exec vite build

FROM python:3.12-alpine@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/backend DATA_DIR=/app/data REFERENCE_DIR=/app/resources TMPDIR=/tmp APP_PORT=8080 APP_MODE=production
LABEL org.opencontainers.image.title="Aptilume" org.opencontainers.image.version="0.6.1" org.opencontainers.image.source="https://github.com/etrkk5/Aptilume"
WORKDIR /app
COPY requirements.lock.txt ./
RUN pip install --no-cache-dir -r requirements.lock.txt && pip uninstall -y pip && rm -rf /usr/local/lib/python3.12/ensurepip
COPY backend/ ./backend/
COPY alembic.ini ./
COPY data/ ./resources/
COPY --from=web-build /build/dist/ ./web/dist/
RUN mkdir -p /app/data && chgrp -R 0 /app && chmod -R g+rX /app && chmod -R go-w /app && chmod 0770 /app/data
USER 1001:0
EXPOSE 8080
HEALTHCHECK --interval=20s --timeout=5s --start-period=60s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health/ready',timeout=3)"
ENTRYPOINT ["python", "-m", "app.cli"]
CMD ["api"]
