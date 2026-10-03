FROM python:3.12-slim

LABEL org.opencontainers.image.source=https://github.com/platypod/finance-pipelines

WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 FINANCE_ROOT=/app

# OCR for payslips printed to PDF without a text layer (5 of the historical ones).
RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils tesseract-ocr tesseract-ocr-fra \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first (cached layer), then the project.
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install .

COPY contracts/ ./contracts/
COPY migrations/ ./migrations/
COPY generated/ ./generated/
COPY dbt/ ./dbt/

# dbt writes target/ and logs/ under temp dirs (see dbt.py); the app dir can stay read-only.
RUN useradd --uid 10001 --no-create-home pipeline
USER 10001

ENTRYPOINT ["pp"]
CMD ["--help"]
