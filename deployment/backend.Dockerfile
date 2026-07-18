# Build context is the repo root (see docker-compose.yml) so this can COPY
# framework_mapping/, which lives alongside backend/, not inside it.
#
# glibc base, not -alpine: lancedb, pyarrow, numpy, scikit-learn, and
# onnxruntime (transitively via fastembed) do not reliably ship musl wheels
# (confirmed against backend/pyproject.toml's actual dependency list).
FROM python:3.12-slim

WORKDIR /app

# Install the backend package (production deps only - the `dev` extras
# group in pyproject.toml, pytest/ruff/httpx, is never installed here).
COPY backend/pyproject.toml ./pyproject.toml
COPY backend/src ./src
RUN pip install --no-cache-dir .

# framework_mapping/ is static, git-tracked reference data (ADR-0002:
# "data as code"), read by services/framework_loader.py at request time -
# baked into the image at build time, not bind-mounted from the host.
COPY framework_mapping/ ./framework_mapping/

# Runtime-writable state (vector store, SQLite db, the ~67MB ONNX model
# cache) lives under /data, backed by docker-compose's named volume so it
# survives container recreation. Each path's parent directory is created
# by the application itself on first use (repositories/vector_repository.py,
# repositories/assessment_repository.py, ai/embeddings.py all call
# mkdir(parents=True, exist_ok=True)) - nothing to pre-create here.
ENV COMPLIANCE_PLATFORM_FRAMEWORK_MAPPING_DIR=/app/framework_mapping \
    COMPLIANCE_PLATFORM_VECTOR_STORE_DIR=/data/lancedb \
    COMPLIANCE_PLATFORM_ASSESSMENTS_DB_PATH=/data/assessments.db \
    COMPLIANCE_PLATFORM_EMBEDDING_MODEL_CACHE_DIR=/data/model_cache

EXPOSE 8000

# R-6: the ONNX embedder's confirmed cold-load is ~7s once cached, longer
# on a genuine first run that also downloads the ~67MB model - start_period
# gives that room before a slow first check counts as unhealthy.
HEALTHCHECK --interval=10s --timeout=5s --start-period=40s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health', timeout=3)" || exit 1

CMD ["uvicorn", "compliance_platform.main:app", "--host", "0.0.0.0", "--port", "8000"]
