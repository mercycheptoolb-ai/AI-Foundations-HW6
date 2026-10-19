"""Campus Customs vendor desk agent (PydanticAI + gpt-6-luna via Portkey).

Usage:
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html                    # all defenses (default)
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses none    # Problem 3 agent, no defenses
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --defenses code,prompt
    python agent.py --doc data/practice_docs/p01_bluehen_quote.html --cache off

Defense layers (Problem 6), any combination:
    code    read_document returns only the text a person would see (sanitize.py)
    design  send_email / approve_payment need human sign-off; the decision and reason come from code (rules.py)
    prompt  the "Security rules" section of prompts/prompt.md is sent (cut off when this layer is off)

Reads one vendor document, returns a VendorDecision, and appends to:
    output/usage_log.json    token counts the API reports + dollar cost from data/prices.json
    output/audit_trail.json  every tool call (args + short result) + the final answer
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from openai import AsyncOpenAI
from pydantic_ai import Agent, DeferredToolRequests, DeferredToolResults, Tool, ToolDenied
from pydantic_ai.messages import ModelResponse
from pydantic_ai.models.openai import OpenAIResponsesModel, OpenAIResponsesModelSettings
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.usage import RequestUsage, RunUsage

import rules
from models import DeskDeps, VendorDecision
from tools import TRAP_FILE, approve_payment, log_trap, read_document, send_email

os.environ.setdefault("PYDANTIC_AI_NO_BANNER", "1")

HERE = Path(__file__).resolve().parent
OUTPUT = HERE / "output"
USAGE_LOG = OUTPUT / "usage_log.json"
AUDIT_TRAIL = OUTPUT / "audit_trail.json"
PRICES = HERE / "data" / "prices.json"
PROMPT = HERE / "prompts" / "prompt.md"
HANDBOOK = HERE / "data" / "shop_handbook.md"

MODEL_NAME = "gpt-6-luna"
PORTKEY_BASE_URL = "https://api.portkey.ai/v1"

# Prompt caching. "on": a fixed cache key routes every call to the same cache, so the handbook prefix is
# reused. "off": no key, plus a random id at the start of the instructions on every request (see
# build_agent). OpenAI's {"mode": "explicit"} switch is ignored by gpt-6-luna via Portkey, so it can't be
# used to turn caching off.
CACHE_SETTINGS: dict[str, OpenAIResponsesModelSettings] = {
    "on": {"openai_prompt_cache_key": "campus-customs-vendor-desk"},
    "off": {},
}

LAYERS = ("code", "design", "prompt")
SECURITY_HEADER = "## Security rules"
MAX_DENIAL_ROUNDS = 3

for folder in [HERE, *HERE.parents]:
    if (folder / ".env").exists():
        load_dotenv(folder / ".env", override=False)


def build_model() -> OpenAIResponsesModel:
    key = os.getenv("PORTKEY_API_KEY", "").strip()
    if not key:
        sys.exit("PORTKEY_API_KEY is missing. Put it in the root .env file.")
    # x-portkey-cache-force-refresh: Portkey otherwise replays a stored response for an identical request
    # (same response id, same tokens), so repeated runs wouldn't be real model calls. OpenAI's own prompt
    # cache (cached input tokens) is separate and still works.
    client = AsyncOpenAI(api_key=key, base_url=PORTKEY_BASE_URL, default_headers={
        "x-portkey-provider": "openai",
        "x-portkey-cache-force-refresh": "true",
    })
    return OpenAIResponsesModel(MODEL_NAME, provider=OpenAIProvider(openai_client=client))


def parse_defenses(spec: str) -> frozenset[str]:
    if spec == "all":
        return frozenset(LAYERS)
    if spec == "none":
        return frozenset()
    layers = frozenset(x.strip() for x in spec.split(",") if x.strip())
    if bad := layers - set(LAYERS):
        raise ValueError(f"unknown defense layer(s): {sorted(bad)}; use all, none, or {','.join(LAYERS)}")
    return layers


def prompt_for(defenses: frozenset[str]) -> str:
    """prompts/prompt.md, with its Security rules section cut off unless the prompt layer is on."""
    text = PROMPT.read_text()
    return text if "prompt" in defenses else text.split(SECURITY_HEADER)[0].rstrip() + "\n"


def build_agent(cache: str = "on", defenses: frozenset[str] = frozenset(LAYERS)) -> Agent[DeskDeps, Any]:
    # Instructions + handbook are identical on every call, so they form a cacheable prefix.
    static = f"{prompt_for(defenses)}\n\n# Campus Customs Shop Handbook\n\n{HANDBOOK.read_text()}"

    def no_cache_instructions() -> str:
        # Rebuilt for every model request: a fresh random id as the very first tokens means no two
        # requests share a prefix, so the handbook can never be read back from the cache.
        return f"Request id: {uuid4().hex}\n\n{static}"

    if "design" in defenses:
        # Design layer: the dangerous tools stay on the system but every call is held for a human sign-off.
        # The model can ask; nothing runs. The run ends with DeferredToolRequests, which run() denies.
        tools = [read_document, Tool(send_email, requires_approval=True), Tool(approve_payment, requires_approval=True)]
        output_type: Any = [VendorDecision, DeferredToolRequests]
    else:
        tools = [read_document, send_email, approve_payment]
        output_type = VendorDecision

    return Agent(
        build_model(),
        deps_type=DeskDeps,
        output_type=output_type,
        instructions=static if cache == "on" else no_cache_instructions,
        tools=tools,
    )


def cost_usd(usage: RunUsage | RequestUsage) -> dict[str, float]:
    p = json.loads(PRICES.read_text())[MODEL_NAME]
    uncached = usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens
    parts = {
        "input": uncached * p["input_per_1m"] / 1e6,
        "cached_input": usage.cache_read_tokens * p["cached_input_per_1m"] / 1e6,
        "cache_write": usage.cache_write_tokens * p["cache_write_per_1m"] / 1e6,
        "output": usage.output_tokens * p["output_per_1m"] / 1e6,
    }
    parts["total"] = sum(parts.values())
    return {k: round(v, 8) for k, v in parts.items()}


def token_counts(usage: RunUsage | RequestUsage) -> dict[str, int]:
    """Every token count the API reports, plus the uncached input the price list needs."""
    return {
        "input_tokens": usage.input_tokens,
        "cached_input_tokens": usage.cache_read_tokens,
        "cache_write_tokens": usage.cache_write_tokens,
        "uncached_input_tokens": usage.input_tokens - usage.cache_read_tokens - usage.cache_write_tokens,
        "output_tokens": usage.output_tokens,
        "reasoning_tokens": usage.details.get("reasoning_tokens", 0),
        "total_tokens": usage.input_tokens + usage.output_tokens,
    }


def append_json(path: Path, entry: dict[str, Any]) -> None:
    rows = json.loads(path.read_text()) if path.exists() else []
    rows.append(entry)
    path.write_text(json.dumps(rows, indent=2) + "\n")


def run(doc: Path, cache: str = "on", defenses: frozenset[str] = frozenset(LAYERS)) -> tuple[VendorDecision, list[dict[str, Any]]]:
    """Run the agent on one document. Returns the answer and one record per model call."""
    OUTPUT.mkdir(exist_ok=True)
    if not TRAP_FILE.exists():
        TRAP_FILE.write_text("[]\n")

    deps = DeskDeps(doc_path=doc, defenses=frozenset(defenses))
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    agent = build_agent(cache, deps.defenses)
    settings = CACHE_SETTINGS[cache]

    result = agent.run_sync(f"Vendor document path: {doc}", deps=deps, model_settings=settings)
    responses = [m for m in result.new_messages() if isinstance(m, ModelResponse)]
    usage = result.usage
    # Design layer: a held send_email / approve_payment call is logged as a blocked attempt and denied
    # (there is no human here to sign off), then the model continues to its answer.
    for _ in range(MAX_DENIAL_ROUNDS):
        if not isinstance(result.output, DeferredToolRequests):
            break
        denials = {}
        for call in result.output.approvals:
            args = call.args_as_dict()
            log_trap(call.tool_name, args, doc, status="blocked")
            deps.audit.append({"tool": call.tool_name, "args": args, "result": "BLOCKED: needs human sign-off; denied."})
            denials[call.tool_call_id] = ToolDenied("Blocked: this action needs a human sign-off and was not performed.")
        result = agent.run_sync(
            message_history=result.all_messages(), deferred_tool_results=DeferredToolResults(approvals=denials),
            deps=deps, model_settings=settings,
        )
        responses += [m for m in result.new_messages() if isinstance(m, ModelResponse)]
        usage = usage + result.usage
    if isinstance(result.output, DeferredToolRequests):
        raise RuntimeError(f"{doc.name}: model kept requesting blocked tools after {MAX_DENIAL_ROUNDS} denials")

    answer: VendorDecision = result.output
    if "design" in deps.defenses:
        # Design layer: the model only supplies facts; code applies the handbook rules and writes the reason.
        model_answer = answer
        answer = rules.decide(model_answer)
        deps.audit.append({
            "tool": "rules.decide (code)",
            "args": {"model_decision": model_answer.decision, "model_reason": model_answer.reason},
            "result": f"{answer.decision}: {answer.reason}",
        })

    calls = [
        {"call": i, "response_id": m.provider_response_id, **token_counts(m.usage), "cost_usd": cost_usd(m.usage)}
        for i, m in enumerate(responses, start=1)
    ]

    doc_name = str(doc.relative_to(HERE)) if doc.is_relative_to(HERE) else str(doc)
    append_json(USAGE_LOG, {
        "document": doc_name,
        "time": started,
        "model": MODEL_NAME,
        "cache": cache,
        "defenses": sorted(deps.defenses),
        "requests": usage.requests,
        **token_counts(usage),
        "cost_usd": cost_usd(usage),
    })
    append_json(AUDIT_TRAIL, {
        "document": doc_name,
        "time": started,
        "defenses": sorted(deps.defenses),
        "tool_calls": deps.audit,
        "final_answer": answer.model_dump(),
    })
    return answer, calls


def main() -> None:
    parser = argparse.ArgumentParser(description="Campus Customs vendor desk agent")
    parser.add_argument("--doc", required=True, help="Path to one vendor document (.html, .pdf, or .eml)")
    parser.add_argument("--cache", choices=["on", "off"], default="on", help="Reuse the handbook from the prompt cache")
    parser.add_argument("--defenses", default="all",
                        help="all (default), none, or a comma list of: code, design, prompt")
    args = parser.parse_args()
    try:
        defenses = parse_defenses(args.defenses)
    except ValueError as e:
        parser.error(str(e))
    doc = Path(args.doc).expanduser()
    if not doc.is_absolute() and not doc.exists():
        doc = HERE / doc  # allow running from outside hw6/
    doc = doc.resolve()
    if not doc.exists():
        sys.exit(f"Document not found: {doc}")

    answer, _ = run(doc, args.cache, defenses)
    print(json.dumps(answer.model_dump(), indent=2))
    usage = json.loads(USAGE_LOG.read_text())[-1]
    print(
        f"\ntokens: {usage['input_tokens']:,} in ({usage['cached_input_tokens']:,} cached) / "
        f"{usage['output_tokens']:,} out  |  cost: ${usage['cost_usd']['total']:.6f}"
    )


if __name__ == "__main__":
    main()
