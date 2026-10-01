# Neonatal Health Bulletin — build targets.
# `make all` is the single command an MoH engineer needs.

PY := PYTHONPATH=src python3
.PHONY: all bulletin profile test clean

all: bulletin           ## Run the pipeline end to end

bulletin:               ## Build output/neonatal_bulletin.html + 13 CSV tables
	python3 src/run.py

profile:                ## Inspect what is actually in data/raw before trusting it
	$(PY) src/ingest.py

test:                   ## Regression suite
	$(PY) -m pytest tests/ -q

clean:                  ## Remove generated artefacts
	rm -rf output/*.html output/tables/*.csv
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
