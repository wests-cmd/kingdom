# Multi-stage Docker build for Kingdom v1.0.0 production runtime

# Stage 0: Audit all checked-in dependency manifests before any package scripts run.
# The audited stage is a prerequisite for BOTH the npm and Python installs.
FROM python:3.12-slim AS dependency-audit
WORKDIR /audit
COPY requirements*.txt ./
COPY scripts/audit_known_compromises.py scripts/audit_known_compromises.py
COPY frontend/package*.json frontend/
COPY desktop/package*.json desktop/
COPY apps/mobile/package.json apps/mobile/
COPY apps/mobile/native/package*.json apps/mobile/native/
RUN python scripts/audit_known_compromises.py && touch /audit-ok

# Stage 1: Build Production Frontend Static Assets
FROM node:24-alpine AS frontend-builder

WORKDIR /app/frontend
COPY --from=dependency-audit /audit-ok /audit-ok

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# Stage 2: Production Python Runtime Environment
FROM python:3.12-slim

WORKDIR /app
COPY --from=dependency-audit /audit-ok /audit-ok

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY requirements.txt .
RUN python -m pip install --no-cache-dir --upgrade pip==26.3 \
    && python -m pip install --no-cache-dir -r requirements.txt

COPY . .

# Copy prebuilt frontend static distribution
COPY --from=frontend-builder /app/frontend/dist /app/frontend/dist

# Audit the actual final image, including packaging tools inherited from its base.
# Native installer audits cannot prove this separate container inventory is safe.
RUN python scripts/audit_known_compromises.py --installed \
    && python scripts/audit_release_dependencies.py

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=5s --retries=3 \
  CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health/ready')" || exit 1

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
