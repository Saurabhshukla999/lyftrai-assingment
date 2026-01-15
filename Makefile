.PHONY: up down logs test clean

up:
	docker compose up -d --build

down:
	docker compose down -v

logs:
	docker compose logs -f api

test:
	python -m pytest tests/ -v

clean:
	docker compose down -v
	rm -rf data/

