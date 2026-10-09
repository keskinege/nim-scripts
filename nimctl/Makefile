.PHONY: test lint build-exe docs docs-serve clean

test:
	uv run pytest

lint:
	uv run ruff check src tests

build-exe:
	uv run pyinstaller --onefile --name nimctl --paths src entry.py

docs:
	uv run python scripts/gen_command_reference.py
	uv run mkdocs build

docs-serve:
	uv run mkdocs serve

clean:
	rm -rf build dist nimctl.spec site