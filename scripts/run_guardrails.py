"""Run the deterministic guardrail test suite for the hotel order agent."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

GUARDRAIL_TESTS = [
    "tests/test_product_store_diagnostics.py",
    "tests/test_product_search_tool.py",
    "tests/test_product_search_api.py",
    "tests/test_product_contract.py",
    "tests/test_service_types.py",
    "tests/test_workflow_routes.py",
    "tests/test_workflow_policy_fixture.py",
    "tests/test_fake_llm_workflow_eval.py",
    "tests/test_ask_response_policy.py",
    "tests/test_confirmation_policy.py",
    "tests/test_coverage_policy.py",
    "tests/test_intent_policy.py",
    "tests/test_message_question_helpers.py",
    "tests/test_order_context_loader.py",
    "tests/test_order_defaults.py",
    "tests/test_order_validation_policy.py",
    "tests/test_product_feedback.py",
    "tests/test_product_search_policy.py",
    "tests/test_product_selection_policy.py",
    "tests/test_session_access.py",
    "tests/test_search_product_node.py",
    "tests/test_product_selection_flow.py",
    "tests/test_order_preview.py",
    "tests/test_order_preview_contract.py",
    "tests/test_order_policy_eval.py",
]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pytest", default=None, help="pytest executable to use; defaults to .venv/bin/pytest or PATH")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Pass -q to pytest.",
    )
    args = parser.parse_args()

    command = resolve_pytest_command(args.pytest)
    if args.quiet:
        command.append("-q")
    command.extend(GUARDRAIL_TESTS)

    print("Running guardrail tests:", flush=True)
    for test_path in GUARDRAIL_TESTS:
        print(f"  - {test_path}", flush=True)
    print(flush=True)
    print("$ " + " ".join(command), flush=True)
    print(flush=True)

    return subprocess.call(command, cwd=PROJECT_ROOT)


def resolve_pytest_command(configured: str | None) -> list[str]:
    if configured:
        pytest_bin = Path(configured)
        return [str(pytest_bin if pytest_bin.is_absolute() else PROJECT_ROOT / pytest_bin)]

    local_pytest = PROJECT_ROOT / ".venv/bin/pytest"
    if local_pytest.exists():
        return [str(local_pytest)]

    path_pytest = shutil.which("pytest")
    if path_pytest:
        return [path_pytest]

    return [sys.executable, "-m", "pytest"]


if __name__ == "__main__":
    raise SystemExit(main())
