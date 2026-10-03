.PHONY: up test build down
up:
	docker compose up --build -d
down:
	docker compose down
test:
	cd backend && python -m pytest -q
build:
	cd frontend && npm ci && npm run build
