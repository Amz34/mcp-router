.PHONY: test benchmark json-demo

test:
	PYTHONPATH=. python3 -m unittest discover -s tests

benchmark:
	python3 -m mcp_router --benchmark

json-demo:
	python3 -m mcp_router "Audit CloudSQL database" --json
