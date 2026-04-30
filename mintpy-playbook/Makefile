# =============================================================================
# MintPy Docker Playbook — Makefile
# =============================================================================

.PHONY: help build run shell jupyter download pipeline analysis figures clean

COMPOSE = docker compose

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

build: ## Build the Docker image
	$(COMPOSE) build

run: ## Run the complete pipeline (download + process + analyze + figures)
	$(COMPOSE) up pipeline

shell: ## Open an interactive shell in the MintPy container
	$(COMPOSE) run --rm mintpy bash

jupyter: ## Start JupyterLab server on port 8888
	$(COMPOSE) up jupyter

download: ## Download the sample dataset only
	$(COMPOSE) run --rm mintpy bash /workspace/scripts/01_download_data.sh

pipeline: ## Run the MintPy smallbaselineApp pipeline
	$(COMPOSE) run --rm mintpy bash /workspace/scripts/02_run_pipeline.sh

analysis: ## Run post-processing analysis
	$(COMPOSE) run --rm mintpy bash /workspace/scripts/03_post_analysis.sh

figures: ## Generate publication-quality figures
	$(COMPOSE) run --rm mintpy python /workspace/scripts/04_generate_figures.py

step-by-step: ## Run pipeline step-by-step with individual logs
	$(COMPOSE) run --rm mintpy bash /workspace/scripts/05_step_by_step_pipeline.sh

info: ## Show info about processed HDF5 files
	$(COMPOSE) run --rm mintpy bash -c " \
		cd /data/FernandinaSenDT128/mintpy && \
		echo '=== Interferogram Stack ===' && info.py inputs/ifgramStack.h5 && \
		echo '=== Time Series ===' && info.py timeseries.h5 && \
		echo '=== Velocity ===' && info.py velocity.h5 \
	"

clean: ## Remove processed data (keeps downloaded archives)
	$(COMPOSE) run --rm mintpy bash -c " \
		cd /data/FernandinaSenDT128/mintpy && \
		rm -rf timeseries*.h5 velocity*.h5 temporalCoherence.h5 \
		       avgSpatialCoh.h5 maskTempCoh.h5 geo/ pic/ \
		       numInvIfgram.h5 avgPhaseVelocity.h5 \
	"

clean-all: ## Remove all data including downloads
	rm -rf data/*

stop: ## Stop all running containers
	$(COMPOSE) down
