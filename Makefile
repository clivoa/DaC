.PHONY: setup validate validate-splunk deploy-dry deploy install-hooks

setup:
	pip install -r requirements.txt
	pre-commit install
	@echo "Setup complete. Configure SPLUNK_URL, SPLUNK_TOKEN in your environment."

validate:
	python scripts/validate.py --all --no-splunk

validate-splunk:
	python scripts/validate.py --all

deploy-dry:
	python scripts/deploy.py --all --dry-run

deploy:
	python scripts/deploy.py --all

install-hooks:
	pre-commit install
