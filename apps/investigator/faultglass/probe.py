import argparse
import signal
import sys

from .context_config import ContextConfig
from .context_errors import ContextUnavailable
from .context_models import evidence_id
from .execution import interrupt
from .graph_repository import GraphRepository
from .jsonio import encode
from .probe_service import execute_probe, plan_probe, saved_action


def interruption_evidence(repository, seed_id):
    from .context_artifacts import load_evidence
    from .planning_artifacts import PlanningStore

    try:
        journal = (
            PlanningStore(repository.config.artifact_root, seed_id).journal()
            if repository
            else None
        )
        if journal is None:
            return "No child comparison was reserved."
        try:
            load_evidence(repository.config.artifact_root, journal.child_evidence_id)
        except (OSError, ValueError):
            return (
                "Child evidence is incomplete. Recover owned engines with python -m faultglass.recover --run-id "
                + journal.child_evidence_id
            )
        return (
            "Child evidence is complete. Save it with python -m faultglass.probe commit --evidence-id "
            + seed_id
        )
    except (OSError, ValueError):
        return "Child evidence could not be verified. Inspect the saved comparison before starting again."


def main():
    parser = argparse.ArgumentParser(
        description="Choose and run an evidence-backed experiment for a saved comparison."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    for name in ("plan", "execute", "inspect", "commit"):
        command = subcommands.add_parser(name)
        command.add_argument("--evidence-id", required=True, type=evidence_id)
    args = parser.parse_args()
    signal.signal(signal.SIGTERM, interrupt)
    repository = None
    try:
        repository = GraphRepository(ContextConfig.from_environment())
        if args.command == "plan":
            print("Reading related investigation evidence…", file=sys.stderr)
            view = plan_probe(repository, args.evidence_id)
        elif args.command == "execute":
            print(
                "Running the selected experiment on baseline and target…",
                file=sys.stderr,
            )
            view = execute_probe(repository, args.evidence_id)
        else:
            view = saved_action(
                repository, args.evidence_id, commit=args.command == "commit"
            )
        plan = view["decision"]
        if view.get("failure"):
            print(
                "The experiment could not be completed. Child evidence is incomplete. Inspect the saved evidence before starting again. "
                + (view.get("recovery_command") or ""),
                file=sys.stderr,
            )
        elif view["commit_pending"]:
            print(
                "Evidence is saved. Restore investigation memory, then save the evidence again. "
                + view["recovery_command"],
                file=sys.stderr,
            )
        elif view["execution_state"] == "incomplete":
            print(
                "A previous experiment did not finish. Child evidence is incomplete. "
                + view["recovery_command"],
                file=sys.stderr,
            )
        elif view.get("result"):
            relationship = view["result"]["relationship"]
            print(
                {
                    "preserved": "Divergence preserved.",
                    "eliminated": "No difference observed for this experiment.",
                    "changed": "A different divergence was observed.",
                }[relationship],
                file=sys.stderr,
            )
        elif view.get("reason") == "budget_exhausted":
            print("The experiment budget was exhausted.", file=sys.stderr)
        elif plan["outcome"] == "not_reproduced":
            print(
                "The original case showed no difference. No experiment was started.",
                file=sys.stderr,
            )
        elif plan["outcome"] == "unresolved":
            print("No supported experiment applies to this case.", file=sys.stderr)
        else:
            if plan["novel"]:
                print(
                    "No verified related investigations yet. Probe ranking uses structural evidence only.",
                    file=sys.stderr,
                )
            print("Selected experiment: " + plan["selected_probe_id"], file=sys.stderr)
        print(encode(view).decode())
        return view.get(
            "exit_code",
            1
            if view["commit_pending"]
            or view.get("failure")
            or view["execution_state"] == "incomplete"
            else 0,
        )
    except KeyboardInterrupt:
        print(
            "The experiment was interrupted. "
            + interruption_evidence(repository, args.evidence_id)
            + " Saved comparison: "
            + args.evidence_id,
            file=sys.stderr,
        )
        return 130
    except (OSError, ValueError, RecursionError) as error:
        message = (
            "Investigation memory is unavailable. Restore the context service and retry."
            if isinstance(error, ContextUnavailable)
            else str(error)
            if type(error).__module__.startswith("faultglass.")
            else "Saved experiment evidence could not be verified. Check the setup instructions and inspect the saved comparison."
        )
        print(message + " Saved comparison: " + args.evidence_id, file=sys.stderr)
        return 1
    finally:
        if repository:
            repository.close()


if __name__ == "__main__":
    sys.exit(main())
