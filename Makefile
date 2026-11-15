.PHONY: help init seed test eval serve ui demo docker-build docker-up clean

help:
	@echo "Available commands:"
	@echo "  make init         - Install dependencies and seed database & vector store"
	@echo "  make seed         - Seed SQLite database and ChromaDB vector store"
	@echo "  make test         - Run 28 unit and integration tests via pytest"
	@echo "  make eval         - Run 10-scenario benchmark evaluation harness"
	@echo "  make serve        - Start FastAPI backend REST API (port 8000)"
	@echo "  make ui           - Start Streamlit interactive web dashboard (port 8501)"
	@echo "  make demo         - Run key scripted demonstration scenarios via CLI"
	@echo "  make docker-build - Build Docker container images"
	@echo "  make docker-up    - Run full stack via Docker Compose"
	@echo "  make clean        - Remove caches, temporary files, and test runs"

init:
	python -m pip install -r requirements.txt
	python -m scdrc.cli seed

seed:
	python -m scdrc.cli seed

test:
	python -m pytest tests/unit tests/integration -v

eval:
	python -u tests/eval/run_eval.py

serve:
	python -m scdrc.cli serve

ui:
	python -m scdrc.cli ui

demo:
	@echo "Running Scenario 1: Primary Supplier Delay..."
	python -m scdrc.cli run --scenario S1
	@echo "Running Scenario 2: Highway Rockslide Corridor Detour..."
	python -m scdrc.cli run --scenario S2
	@echo "Running Scenario 5: Trap Case - Cheapest Option Arrives Late..."
	python -m scdrc.cli run --scenario S5
	@echo "Running Scenario 6: Contract Exclusivity Clause 4.2 Exclusion..."
	python -m scdrc.cli run --scenario S6

docker-build:
	docker compose build

docker-up:
	docker compose up -d

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	rm -rf outputs/EVAL-* outputs/DEBUG-* outputs/TEST-*
