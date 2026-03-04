.PHONY: help install dev test run api clean sample docs

help:
	@echo "Review Prep Engine - Make Commands"
	@echo ""
	@echo "  make install     - Install dependencies"
	@echo "  make sample      - Load sample data and generate briefings"
	@echo "  make api         - Start FastAPI development server (port 8000)"
	@echo "  make test        - Run tests (future)"
	@echo "  make clean       - Remove generated files and cache"
	@echo "  make docs        - Open documentation"

install:
	pip install -r requirements.txt

sample:
	python sample_data/load_sample.py

api:
	uvicorn api.app:app --reload --host 0.0.0.0 --port 8000

test:
	@echo "Tests coming in phase 2"

clean:
	rm -rf __pycache__ .pytest_cache
	rm -rf data/
	find . -name "*.pyc" -delete
	find . -name ".DS_Store" -delete

docs:
	@echo "Documentation:"
	@echo "  docs/PRD.md - Product Requirements"
	@echo "  docs/ARCHITECTURE.md - System Design"
	@echo "  docs/DECISION_LOG.md - Design Decisions"

# Development targets
dev-install:
	pip install -r requirements.txt
	pip install pytest pytest-cov black flake8

format:
	black src/ importers/ storage/ api/ export/ sample_data/

lint:
	flake8 src/ importers/ storage/ api/ export/ sample_data/ --max-line-length=100

# Docker targets
docker-build:
	docker build -t review-prep-engine:latest .

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f api
