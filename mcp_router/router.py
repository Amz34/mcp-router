#!/usr/bin/env python3
"""
mcp-router: Production-Grade Dynamic MCP Router, Scope Isolator & Token Containment Engine.
Eliminates upfront tool schema token burn (30k-60k tokens) by routing only task-relevant MCP tools.
Inspired by microsoft/mcp-gateway and smart-mcp-proxy.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, asdict
from typing import List, Dict, Any, Optional, Set

# Domain intent keywords for heuristic dynamic classification
INTENT_PATTERNS = {
    "gcp_spanner": [r"\bspanner\b", r"\bddl\b.*spanner", r"\bdatabase_schema\b"],
    "gcp_bigquery": [r"\bbigquery\b", r"\bbq\b", r"\bdataset\b", r"\bquery_results\b"],
    "gcp_cloudsql": [r"\bcloudsql\b", r"\bpostgres\b", r"\bmysql\b", r"\bcloud\s*sql\b"],
    "gcp_alloydb": [r"\balloydb\b", r"\balloy\b"],
    "gcp_bigtable": [r"\bbigtable\b", r"\btablets\b", r"\browkey\b"],
    "gcp_gcs": [r"\bgcs\b", r"\bgs://", r"\bbucket\b", r"\bcloud\s*storage\b"],
    "gcp_kc": [r"\bknowledge\s*catalog\b", r"\bdataplex\b", r"\bglossary\b", r"\bentry_group\b"],
    "notebook": [r"\bipynb\b", r"\bjupyter\b", r"\bnotebook\b"],
    "hub_invertio": [r"\binvertio\b", r"\bclient\s*leads\b", r"\boutreach\b"],
    "cloud_assist": [r"\barchitecture\b", r"\bdesign\s*center\b", r"\bbest\s*practices\b", r"\bcloud\s*advisor\b"],
}

SERVER_CATEGORY_MAP = {
    "dak_dak-alloydb": "gcp_alloydb",
    "dak_dak-spanner": "gcp_spanner",
    "dak_dak-cloudsql": "gcp_cloudsql",
    "dak_dak-bigtable": "gcp_bigtable",
    "dak_dak-bigtable-data": "gcp_bigtable",
    "dak_dak-bigquery": "gcp_bigquery",
    "dak_dak-gcs": "gcp_gcs",
    "dak_dak-kc": "gcp_kc",
    "dak_dak-notebook": "notebook",
    "invertio-hub": "hub_invertio",
    "gemini_cloud_assist": "cloud_assist",
    "application_design_center": "cloud_assist",
}

# Fallback catalog when running in clean CI / test runner environments
FALLBACK_CATALOG = {
    "dak_dak-alloydb": 17,
    "dak_dak-spanner": 16,
    "dak_dak-cloudsql": 15,
    "dak_dak-bigtable": 14,
    "dak_dak-bigtable-data": 1,
    "dak_dak-bigquery": 9,
    "dak_dak-gcs": 10,
    "dak_dak-kc": 17,
    "dak_dak-notebook": 9,
    "invertio-hub": 13,
    "gemini_cloud_assist": 8,
    "application_design_center": 6,
}

ESTIMATED_TOKENS_PER_TOOL_SCHEMA = 350  # Average tokens per JSON schema definition


@dataclass
class RouteDecision:
    prompt_intent: str
    active_servers: List[str]
    suppressed_servers: List[str]
    total_tools_available: int
    tools_selected: int
    tools_masked: int
    estimated_tokens_saved: int
    token_savings_pct: float
    routing_latency_ms: float


def detect_intent(task_prompt: str) -> Set[str]:
    task_lower = task_prompt.lower()
    matched_intents = set()

    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, task_lower):
                matched_intents.add(intent)
                break

    return matched_intents


def get_available_mcp_servers(mcp_base_dir: Optional[str] = None) -> Dict[str, int]:
    target_dir = mcp_base_dir or os.environ.get(
        "MCP_BASE_DIR",
        os.path.expanduser("~/.gemini/antigravity-cli/mcp")
    )
    servers = {}
    if os.path.exists(target_dir):
        for entry in os.listdir(target_dir):
            full_p = os.path.join(target_dir, entry)
            if os.path.isdir(full_p):
                json_files = [f for f in os.listdir(full_p) if f.endswith(".json")]
                if json_files or entry in SERVER_CATEGORY_MAP:
                    servers[entry] = len(json_files) if json_files else FALLBACK_CATALOG.get(entry, 5)

    if not servers:
        # Graceful fallback to standard catalog in clean environments (e.g. CI)
        servers = dict(FALLBACK_CATALOG)

    return servers


def route_mcp_tools(
    task_prompt: str,
    explicit_profile: Optional[str] = None,
    mcp_base_dir: Optional[str] = None
) -> RouteDecision:
    t0 = time.perf_counter()

    available_servers = get_available_mcp_servers(mcp_base_dir)
    total_tools = sum(available_servers.values())

    active_servers = []
    suppressed_servers = []

    if explicit_profile:
        # Predefined scoped profiles
        profile_lower = explicit_profile.lower()
        if profile_lower in ("minimal", "none", "code", "local"):
            active_servers = []
            suppressed_servers = list(available_servers.keys())
        elif profile_lower in ("data", "analytics"):
            target_cats = {"gcp_bigquery", "gcp_gcs", "notebook"}
            for s in available_servers:
                if SERVER_CATEGORY_MAP.get(s) in target_cats:
                    active_servers.append(s)
                else:
                    suppressed_servers.append(s)
        elif profile_lower in ("db", "database"):
            target_cats = {"gcp_spanner", "gcp_cloudsql", "gcp_alloydb", "gcp_bigtable"}
            for s in available_servers:
                if SERVER_CATEGORY_MAP.get(s) in target_cats:
                    active_servers.append(s)
                else:
                    suppressed_servers.append(s)
        else:
            # Fallback to all
            active_servers = list(available_servers.keys())
    else:
        # Dynamic Intent-based routing
        intents = detect_intent(task_prompt)
        if not intents:
            # If no specialized database or cloud keyword is found, default to minimal footprint!
            # Pure coding, maintenance, bash, or general reasoning requires ZERO heavy GCP schemas
            active_servers = []
            suppressed_servers = list(available_servers.keys())
            detected_label = "general_code_and_bash"
        else:
            detected_label = "+".join(sorted(intents))
            for s in available_servers:
                cat = SERVER_CATEGORY_MAP.get(s)
                if cat in intents:
                    active_servers.append(s)
                else:
                    suppressed_servers.append(s)

    selected_tools = sum(available_servers[s] for s in active_servers)
    masked_tools = total_tools - selected_tools
    tokens_saved = masked_tools * ESTIMATED_TOKENS_PER_TOOL_SCHEMA
    pct_saved = (masked_tools / total_tools * 100.0) if total_tools > 0 else 0.0

    latency_ms = (time.perf_counter() - t0) * 1000.0

    return RouteDecision(
        prompt_intent=explicit_profile if explicit_profile else (detected_label if "detected_label" in locals() else "dynamic"),
        active_servers=active_servers,
        suppressed_servers=suppressed_servers,
        total_tools_available=total_tools,
        tools_selected=selected_tools,
        tools_masked=masked_tools,
        estimated_tokens_saved=tokens_saved,
        token_savings_pct=round(pct_saved, 1),
        routing_latency_ms=round(latency_ms, 3),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="mcp-router: Dynamic MCP Router, Scope Isolator & Token Containment Engine"
    )
    parser.add_argument("prompt", nargs="?", default="", help="Task prompt or user request string")
    parser.add_argument("--profile", choices=["minimal", "data", "db", "all"], help="Explicit scope profile")
    parser.add_argument("--json", action="store_true", help="Output routing decision as machine-readable JSON")
    parser.add_argument("--benchmark", action="store_true", help="Run benchmark across common enterprise workloads")

    args = parser.parse_args()

    if args.benchmark:
        test_prompts = [
            ("Bugfix Python script in repo", "minimal"),
            ("Run BigQuery SQL to calculate revenue by customer", "data"),
            ("Inspect Spanner database schema DDL migrations", "db"),
            ("Deploy landing page to Cloudflare Pages", "minimal"),
            ("Query GCS bucket gs://my-bucket/data.csv", "data"),
        ]
        print("==========================================================================================")
        print(" mcp-router - Enterprise Dynamic Scope Routing Benchmark")
        print("==========================================================================================")
        for p, expected in test_prompts:
            res = route_mcp_tools(p)
            print(f"Task: '{p}'")
            print(f"  -> Intent: {res.prompt_intent:<25} | Active: {len(res.active_servers)} servers ({res.tools_selected} tools)")
            print(f"  -> Tokens Saved: {res.estimated_tokens_saved:,} tokens ({res.token_savings_pct}%) | Latency: {res.routing_latency_ms}ms\n")
        return 0

    if not args.prompt and not args.profile:
        parser.print_help()
        return 1

    decision = route_mcp_tools(args.prompt, explicit_profile=args.profile)

    if args.json:
        print(json.dumps(asdict(decision), indent=2))
        return 0

    print("==========================================================================")
    print(" mcp-router - Dynamic Tool Scope & Token Routing Result")
    print("==========================================================================")
    print(f"Intent / Profile       : {decision.prompt_intent}")
    print(f"Total Available Tools  : {decision.total_tools_available} tools")
    print(f"Active Tools Selected  : {decision.tools_selected} tools ({len(decision.active_servers)} servers)")
    print(f"Suppressed (Kicked)    : {decision.tools_masked} tools ({len(decision.suppressed_servers)} servers)")
    print(f"Estimated Tokens Saved : {decision.estimated_tokens_saved:,} tokens ({decision.token_savings_pct}% context reduction)")
    print(f"Router Overhead Latency: {decision.routing_latency_ms} ms (Sub-millisecond)")
    print("--------------------------------------------------------------------------")
    if decision.active_servers:
        print("Active MCP Servers:")
        for s in decision.active_servers:
            print(f"  [+] {s}")
    else:
        print("Active MCP Servers: None (100% zero-token lightweight local execution)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
