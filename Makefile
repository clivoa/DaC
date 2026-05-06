.PHONY: setup validate validate-splunk deploy-dry deploy runner-build runner-up runner-down

setup:
	pip3 install -r requirements.txt
	pre-commit install
	@echo "Setup complete. Set SPLUNK_URL and SPLUNK_TOKEN in your environment."

validate:
	python3 scripts/validate.py --all --no-splunk

validate-splunk:
	python3 scripts/validate.py --all

deploy-dry:
	python3 scripts/deploy.py --all --dry-run

deploy:
	python3 scripts/deploy.py --all

runner-build:
	docker compose build

runner-up:
	docker compose up -d

runner-down:
	docker compose down
