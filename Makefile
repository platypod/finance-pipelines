# finance-pipelines — local development. Needs: uv, docker.
PG_PORT ?= 55433
VENV    := .venv
PYTHON  := $(VENV)/bin/python
PP      := $(VENV)/bin/pp

# Throwaway Postgres + the same roles the cluster creates (see stack/src/finance).
export FINANCE_PG_HOST     ?= localhost
export FINANCE_PG_PORT     ?= $(PG_PORT)
export FINANCE_PG_USER     ?= postgres
export FINANCE_PG_PASSWORD ?= admin
export FINANCE_PG_ADMIN_USER ?= postgres
export FINANCE_PG_ADMIN_PASSWORD ?= admin
export FINANCE_PG_INGEST_USER ?= finance_ingest
export FINANCE_PG_INGEST_PASSWORD ?= i
export FINANCE_PG_TRANSFORM_USER ?= finance_transform
export FINANCE_PG_TRANSFORM_PASSWORD ?= t

.PHONY: help install generate check lint test test-integration pg-up pg-down image
help:
	@grep -E '^[a-z-]+:' Makefile | cut -d: -f1 | tr '\n' ' '; echo

install:                       ## venv + editable install
	uv venv --python 3.12 $(VENV) -q
	uv pip install -q --python $(PYTHON) -e ".[dev]"

generate:                      ## contracts -> generated/ddl + dbt/models/**/*.yml
	$(PP) generate

check: lint                    ## CI gate: contracts valid and generated files in sync
	$(PP) generate --check

lint:
	$(PP) lint

test:                          ## unit tests (no database)
	$(PYTHON) -m pytest -q -m "not integration"

pg-up:                         ## throwaway Postgres with the cluster's roles
	docker rm -f pp-pg >/dev/null 2>&1 || true
	docker run -d --name pp-pg -e POSTGRES_PASSWORD=$(FINANCE_PG_PASSWORD) -e POSTGRES_DB=finance -p $(PG_PORT):5432 postgres:17-alpine >/dev/null
	@until docker exec pp-pg pg_isready -U postgres -q; do sleep 1; done; sleep 2
	docker exec pp-pg psql -U postgres -d finance -q -c "create role finance_ingest login password 'i'; create role finance_transform login password 't'; create role finance_grafana login password 'g';"

pg-down:
	docker rm -f pp-pg

test-integration: pg-up        ## full suite against the throwaway Postgres
	$(PYTHON) -m pytest -q

image:                         ## local image build
	docker build -t finance-pipelines:dev .
