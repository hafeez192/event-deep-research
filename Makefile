



dev:
	source .venv/bin/activate && uvx --refresh --from "langgraph-cli[inmem]" --with-editable . --python 3.12 langgraph dev 



test: 	
	uv run pytest -v -s