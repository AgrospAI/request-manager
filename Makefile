cov-xml:
	uv run pytest --cov=request_manager tests/ --cov-report=xml


cov:
	uv run pytest --cov=request_manager tests/; rm -f .coverage