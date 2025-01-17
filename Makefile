SHELL := /bin/bash
PY ?= python3
EVENTS ?= 10000000
START ?= 2024-06-01
DAYS ?= 30
END ?= 2024-06-30
JDBC_PACKAGE ?= com.clickhouse:clickhouse-jdbc:0.6.3

.PHONY: up down generate pipeline pipeline-cluster test test-pipeline test-api dashboard

up:            ## start ClickHouse, Spark, API and dashboard
	docker compose up -d --build

down:
	docker compose down

generate:      ## synthesize raw events (set EVENTS=100000000 for the full-scale run)
	cd pipeline && $(PY) -m sparkhouse.generate --events $(EVENTS) --start-date $(START) --days $(DAYS) --output ../data/raw/events

pipeline:      ## run the batch pipeline locally and load ClickHouse
	cd pipeline && SPARKHOUSE_DATA_DIR=../data $(PY) -m sparkhouse.jobs.run_pipeline --start-date $(START) --end-date $(END)

pipeline-cluster: ## submit to the dockerised Spark cluster
	cd pipeline && zip -qr ../data/sparkhouse.zip sparkhouse
	docker compose exec -e CLICKHOUSE_HOST=clickhouse -e SPARKHOUSE_DATA_DIR=/opt/sparkhouse/data \
	  -e SPARK_MASTER=spark://spark-master:7077 spark-master \
	  spark-submit --master spark://spark-master:7077 --packages $(JDBC_PACKAGE) \
	  --py-files /opt/sparkhouse/data/sparkhouse.zip \
	  /opt/sparkhouse/pipeline/sparkhouse/jobs/run_pipeline.py --start-date $(START) --end-date $(END)

test: test-pipeline test-api

test-pipeline:
	cd pipeline && $(PY) -m pytest -q

test-api:
	cd api && $(PY) -m pytest -q

dashboard:     ## run the dashboard dev server
	cd dashboard && npm install && npm run dev
