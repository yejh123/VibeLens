"""Standalone skill proposal + deep creation test script.

Run: PYTHONPATH=src python -u tests/skill/run_test.py
"""

import asyncio
import json
import time
from pathlib import Path

from vibelens.config.llm_config import load_llm_config
from vibelens.llm.backends import create_backend_from_llm_config
from vibelens.llm.prompts.skill_deep_creation import SKILL_DEEP_CREATION_PROMPT
from vibelens.llm.prompts.skill_proposal import SKILL_PROPOSAL_PROMPT
from vibelens.llm.tokenizer import count_tokens
from vibelens.models.inference import InferenceRequest
from vibelens.models.skill import SkillDeepCreationOutput, SkillProposalOutput
from vibelens.models.trajectories import Trajectory
from vibelens.services.context_extraction import extract_session_context
from vibelens.services.friction.digest import format_batch_digest
from vibelens.services.session_batcher import build_batches
from vibelens.utils.json_extract import extract_json as _extract_json

EXAMPLES_DIR = Path("examples/claude-codex-example/parsed")
LOG_DIR = Path("logs/skill/test_run")


def load_sessions(count: int = 2) -> list:
    """Load example trajectory groups."""
    json_files = sorted(EXAMPLES_DIR.glob("*.json"))
    session_files = [f for f in json_files if not f.name.endswith(".meta.json")]

    groups: dict[str, list[Trajectory]] = {}
    for fp in session_files[:count]:
        data = json.loads(fp.read_text())
        trajs = [
            Trajectory.model_validate(item)
            for item in (data if isinstance(data, list) else [data])
        ]
        for t in trajs:
            groups.setdefault(t.session_id, []).append(t)
    return list(groups.values())


def save_log(filename: str, content: str) -> None:
    """Save to log directory."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    (LOG_DIR / filename).write_text(content, encoding="utf-8")


def run_proposal_test(backend) -> SkillProposalOutput | None:
    """Run skill proposal inference and return parsed output."""
    print("\n=== SKILL PROPOSAL TEST ===", flush=True)

    groups = load_sessions(count=2)
    contexts = [extract_session_context(group) for group in groups]
    batches = build_batches(contexts)
    print(f"Sessions: {len(groups)}, Batches: {len(batches)}", flush=True)

    batch = batches[0]
    digest = format_batch_digest(batch)
    output_schema = json.dumps(
        SKILL_PROPOSAL_PROMPT.output_model.model_json_schema(), indent=2
    )
    system_prompt = SKILL_PROPOSAL_PROMPT.render_system()
    user_prompt = SKILL_PROPOSAL_PROMPT.render_user(
        session_count=len(batch.session_contexts),
        session_digest=digest,
        output_schema=output_schema,
        installed_skills=None,
    )

    prompt_tokens = count_tokens(system_prompt + "\n\n" + user_prompt)
    print(f"Prompt tokens: {prompt_tokens:,}", flush=True)

    save_log("proposal_system.txt", system_prompt)
    save_log("proposal_user.txt", user_prompt)

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=4096,
        timeout=180,
        json_schema=SKILL_PROPOSAL_PROMPT.output_model.model_json_schema(),
    )

    start = time.monotonic()
    result = asyncio.run(backend.generate(request))
    elapsed = time.monotonic() - start

    print(f"Duration: {elapsed:.1f}s", flush=True)
    print(f"Model: {result.model}", flush=True)
    if result.cost_usd:
        print(f"Cost: ${result.cost_usd:.4f}", flush=True)
    if result.usage:
        in_tok, out_tok = result.usage.input_tokens, result.usage.output_tokens
        print(f"Tokens: in={in_tok}, out={out_tok}", flush=True)
    print(f"Output length: {len(result.text)} chars", flush=True)

    save_log("proposal_raw.txt", result.text)
    save_log("proposal_metadata.json", json.dumps({
        "model": result.model,
        "duration_ms": result.duration_ms,
        "usage": result.usage.model_dump() if result.usage else None,
        "cost_usd": result.cost_usd,
    }, indent=2))

    # Parse
    try:
        json_str = _extract_json(result.text.strip())
        data = json.loads(json_str)
        output = SkillProposalOutput.model_validate(data)
    except Exception as exc:
        print(f"PARSE ERROR: {exc}", flush=True)
        save_log("proposal_error.txt", str(exc))
        print(f"Raw output preview: {result.text[:500]}", flush=True)
        return None

    save_log("proposal_parsed.json", json.dumps(output.model_dump(), indent=2, default=str))

    print(f"\nPatterns: {len(output.workflow_patterns)}", flush=True)
    for p in output.workflow_patterns:
        desc = p.description[:80]
        print(f"  PATTERN: {p.title} | refs={len(p.example_refs)} | {desc}", flush=True)

    print(f"\nProposals: {len(output.proposals)}", flush=True)
    for p in output.proposals:
        print(f"  PROPOSAL: {p.name} | {p.description[:80]}", flush=True)
        print(f"    rationale: {p.rationale[:100]}", flush=True)
        print(f"    addresses: {p.addressed_patterns}", flush=True)

    print(f"\nSummary: {output.summary[:200]}", flush=True)
    print(f"User profile: {output.user_profile[:200]}", flush=True)
    return output


def run_deep_creation_test(backend, proposal_output: SkillProposalOutput) -> None:
    """Run deep creation for the first proposal."""
    if not proposal_output.proposals:
        print("No proposals to test deep creation", flush=True)
        return

    proposal = proposal_output.proposals[0]
    print(f"\n=== DEEP CREATION: {proposal.name} ===", flush=True)

    groups = load_sessions(count=2)
    contexts = [extract_session_context(group) for group in groups]
    digest = "\n\n".join(ctx.context_text for ctx in contexts)

    output_schema = json.dumps(
        SKILL_DEEP_CREATION_PROMPT.output_model.model_json_schema(), indent=2
    )
    system_prompt = SKILL_DEEP_CREATION_PROMPT.render_system()
    user_prompt = SKILL_DEEP_CREATION_PROMPT.render_user(
        proposal_name=proposal.name,
        proposal_description=proposal.description,
        proposal_rationale=proposal.rationale,
        addressed_patterns=proposal.addressed_patterns,
        session_digest=digest,
        installed_skills=None,
        output_schema=output_schema,
    )

    prompt_tokens = count_tokens(system_prompt + "\n\n" + user_prompt)
    print(f"Prompt tokens: {prompt_tokens:,}", flush=True)

    save_log("deep_creation_system.txt", system_prompt)
    save_log("deep_creation_user.txt", user_prompt)

    request = InferenceRequest(
        system=system_prompt,
        user=user_prompt,
        max_tokens=4096,
        timeout=120,
        json_schema=SKILL_DEEP_CREATION_PROMPT.output_model.model_json_schema(),
    )

    start = time.monotonic()
    result = asyncio.run(backend.generate(request))
    elapsed = time.monotonic() - start

    print(f"Duration: {elapsed:.1f}s", flush=True)
    print(f"Model: {result.model}", flush=True)
    if result.cost_usd:
        print(f"Cost: ${result.cost_usd:.4f}", flush=True)

    save_log("deep_creation_raw.txt", result.text)

    try:
        json_str = _extract_json(result.text.strip())
        data = json.loads(json_str)
        output = SkillDeepCreationOutput.model_validate(data)
    except Exception as exc:
        print(f"PARSE ERROR: {exc}", flush=True)
        save_log("deep_creation_error.txt", str(exc))
        print(f"Raw output preview: {result.text[:500]}", flush=True)
        return

    save_log("deep_creation_parsed.json", json.dumps(output.model_dump(), indent=2, default=str))

    print(f"\nName: {output.name}", flush=True)
    print(f"Description: {output.description}", flush=True)
    print(f"Tools: {output.tools_used}", flush=True)
    print(f"Rationale: {output.rationale[:200]}", flush=True)
    print(f"\nSKILL.md ({len(output.skill_md_content)} chars):", flush=True)
    print(output.skill_md_content, flush=True)


def main() -> None:
    """Run all tests."""
    config = load_llm_config()
    backend = create_backend_from_llm_config(config)
    if backend is None:
        print("No backend configured (disabled). Exiting.")
        return

    print(f"Backend: {type(backend).__name__}", flush=True)

    proposal_output = run_proposal_test(backend)
    if proposal_output:
        run_deep_creation_test(backend, proposal_output)

    print(f"\nAll logs saved to: {LOG_DIR}", flush=True)


if __name__ == "__main__":
    main()
