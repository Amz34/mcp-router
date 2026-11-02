# mcp-router

[![CI](https://github.com/Amz34/mcp-router/actions/workflows/ci.yml/badge.svg)](https://github.com/Amz34/mcp-router/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](#)

`mcp-router` is a high-speed, sub-millisecond dynamic router, scope isolator, and context-window token containment engine for the Model Context Protocol (MCP).

Inspired by enterprise control planes ([`microsoft/mcp-gateway`](https://github.com/microsoft/mcp-gateway) and [`smart-mcp-proxy`](https://github.com/smart-mcp-proxy/mcpproxy-go)), `mcp-router` eliminates upfront tool schema token burn (30,000 to 60,000+ tokens per interaction) by actively masking unneeded MCP schemas and dynamically injecting only the tools required for the task.

---

## The Problem: The Upfront Context Tax

Connecting comprehensive MCP servers (e.g. database engines, cloud SDKs, ticketing tools) into AI coding agents (Claude Code, Antigravity, Cursor) injects every tool schema definition into the model prompt on every turn:
- **130+ Tool Schemas** ≈ **45,000+ tokens consumed** before reading a single line of user instructions.
- **Context Degradation**: Small and frontier models suffer from tool confusion, hallucinating signatures when overwhelmed by dozens of unnecessary tools.
- **Cost Multiplier**: In multi-turn autonomous loops, repeating tens of thousands of schema tokens drains budget and inflates latency.

---

## The Solution: Dynamic Intent Routing & Scope Profiles

`mcp-router` intercepts agent tasks, detects domain intent in sub-millisecond latency, and applies task-specific scopes:

```
                      ┌────────────────────────────────┐
                      │    Incoming Agent Prompt       │
                      │ ("Fix python unit test in git")│
                      └───────────────┬────────────────┘
                                      │
                                      ▼
                        Sub-millisecond Intent Router
                                      │
               ┌──────────────────────┼──────────────────────┐
               ▼                      ▼                      ▼
        [Database Task]         [Data Pipeline]        [Standard Coding]
      Inject: Spanner,        Inject: BigQuery,       Inject: ZERO MCPs
      CloudSQL, AlloyDB       GCS, Notebook           (100% Zero-Token Mode)
      (Mask 110+ tools)       (Mask 115+ tools)       (Mask ALL 135 tools)
               │                      │                      │
               └──────────────────────┼──────────────────────┘
                                      ▼
                     Savings: Up to 45,000 Tokens/Turn
                        Speedup: 3x Response Latency
```

---

## Features

- **Sub-Millisecond Heuristic Router**: Classifies prompts and selects servers in `< 1.0 ms` with zero external API calls.
- **Scoped Profiles**: Predefined isolated profiles (`minimal`, `data`, `database`, `all`).
- **Telemetry & JSON Mode**: Emits structured token savings telemetry ready for Grafana, SRE watchdogs, or Telegram bots (`@AzGem_Bot`).
- **Zero External Dependencies**: Standard Python 3.10+ stdlib only.

---

## Usage

```bash
# Run benchmark across enterprise workloads
python3 -m mcp_router --benchmark

# Test dynamic routing for a specific prompt
python3 -m mcp_router "Inspect CloudSQL postgres schema migrations"

# Enforce a minimal zero-token profile for git/bash tasks
python3 -m mcp_router --profile minimal

# Output JSON for agentic hook orchestration
python3 -m mcp_router "Query BigQuery revenue dataset" --json
```

---

## Benchmark Results

| Workload | Intent Detected | Active Tools | Tokens Saved | Context Reduction | Latency |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Pure Code / Bash** | `general_code_and_bash` | 0 | **43,750 tokens** | **100.0%** | `0.15 ms` |
| **BigQuery Analytics** | `gcp_bigquery` | 9 | **40,600 tokens** | **92.8%** | `0.21 ms` |
| **Spanner DDL Migration** | `gcp_spanner` | 16 | **38,150 tokens** | **87.2%** | `0.23 ms` |

---

## Testing

```bash
PYTHONPATH=. python3 -m unittest discover -s tests
```

---

## License

MIT © [Aamir Zameer (Amz34)](https://github.com/Amz34)

---

Part of [my always-on agent stack](https://github.com/Amz34) · [Awesome Agent Infrastructure](https://github.com/Amz34/awesome-agent-infrastructure) (135 live-checked building blocks).
