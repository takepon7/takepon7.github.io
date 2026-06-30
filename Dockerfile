FROM node:22-bookworm-slim AS web-build

WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY web ./web
RUN npm ci && npm run build

FROM python:3.10-slim AS runtime

WORKDIR /app
ENV PYTHONUNBUFFERED=1
ENV GITAI_STATIC_DIR=/app/web/dist
ENV GITAI_RUNTIME_DB=/data/gitai.sqlite
ENV GITAI_IMAGE_STORE=/data/submissions
ENV GITAI_MODEL=heuristic
ENV GITAI_OCR=fingerprint
ENV GITAI_MODERATION=fingerprint
ENV GITAI_LAYER2_ACTOR=null

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data
COPY --from=web-build /app/web/dist ./web/dist

RUN pip install --no-cache-dir -e ".[api]"
RUN adduser --system --group gitai \
  && mkdir -p /data \
  && chown -R gitai:gitai /app /data

EXPOSE 8000
USER gitai
HEALTHCHECK --interval=30s --timeout=3s --start-period=20s --retries=3 \
  CMD python -c "import json, urllib.request; data=json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)); raise SystemExit(0 if data.get('status') == 'ok' else 1)"
CMD ["uvicorn", "gitai_phase0.server:app", "--host", "0.0.0.0", "--port", "8000"]
