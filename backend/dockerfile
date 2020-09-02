FROM python:3.8-slim-buster as compile-stage

ENV PYTHONFAULTHANDLER=1 \
  PYTHONHASHSEED=random \
  PYTHONUNBUFFERED=1 \
  PIP_DEFAULT_TIMEOUT=100 \
  PIP_DISABLE_PIP_VERSION_CHECK=1 \
  PIP_NO_CACHE_DIR=1

WORKDIR /backend
RUN python -m pip install shiv

COPY . .
RUN python build_backend.py

FROM python:3.8-slim-buster as prod-stage
WORKDIR /app
COPY --from=compile-stage /backend/ssbackend.pyz .
CMD ["python", "ssbackend.pyz"]