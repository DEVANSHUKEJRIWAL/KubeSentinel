# KubeSentinel forecasting benchmark -- re-runnable without a cluster.
# Override PY to point at your venv, e.g.  make test PY=ml-predictor/venv/bin/python
PY  ?= ml-predictor/venv/bin/python
SRC := ml-predictor/src

.PHONY: help venv test eval eval-prom sample compare clean

help:
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | sed 's/:.*##/\t/'

venv: ## create ml-predictor/venv and install deps
	python3 -m venv ml-predictor/venv
	ml-predictor/venv/bin/pip install -r ml-predictor/requirements.txt

test: ## run forecasting unit tests (no cluster needed)
	$(PY) ml-predictor/tests/test_forecasting.py

eval: ## walk-forward eval on the committed SYNTHETIC sample -> benchmarks/forecast_eval.*
	$(PY) $(SRC)/evaluate.py --source benchmarks/cpu_series_sample.csv

eval-prom: ## walk-forward eval on a live Prometheus capture (needs port-forward:9090) -> the real resume number
	$(PY) $(SRC)/evaluate.py --source prometheus

sample: ## regenerate the synthetic sample series
	$(PY) $(SRC)/evaluate.py --gen benchmarks/cpu_series_sample.csv

compare: ## overlay predictive-vs-reactive capture files -> benchmarks/compare.{png,md} (needs matplotlib + capture files)
	$(PY) benchmarks/compare.py

clean: ## remove generated eval reports
	rm -f benchmarks/forecast_eval.json benchmarks/forecast_eval.md
