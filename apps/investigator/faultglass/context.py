import argparse
import signal
import sys

from .context_config import ContextConfig
from .context_errors import ContextError
from .context_models import evidence_id, fingerprint_id
from .execution import interrupt
from .graph_repository import GraphRepository
from .jsonio import encode


def comparison_argument(value):
    try:
        return evidence_id(value)
    except ValueError:
        raise argparse.ArgumentTypeError(
            "Choose a valid saved comparison ID."
        ) from None


def fingerprint_argument(value):
    try:
        return fingerprint_id(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Choose a valid fingerprint ID.") from None


def history_limit(value):
    try:
        limit = int(value)
        if 1 <= limit <= 100:
            return limit
    except ValueError:
        pass
    raise argparse.ArgumentTypeError("Choose a history limit from 1 to 100.")


def main():
    parser = argparse.ArgumentParser(
        description="Save and inspect reusable case context."
    )
    sub = parser.add_subparsers(dest="operation", required=True)
    sub.add_parser(
        "bootstrap", help="Prepare investigation memory without resetting it."
    )
    for command in ("record", "inspect"):
        command_parser = sub.add_parser(command)
        command_parser.add_argument(
            "--evidence-id", type=comparison_argument, required=True
        )
    history = sub.add_parser("history")
    history.add_argument("--fingerprint", type=fingerprint_argument, required=True)
    history.add_argument("--limit", type=history_limit, default=25, metavar="1-100")
    args = parser.parse_args()
    repository = None
    signal.signal(signal.SIGTERM, interrupt)
    try:
        try:
            config = ContextConfig.from_environment()
        except (ValueError, TypeError):
            raise ContextError(
                "Check the investigation memory configuration in the setup instructions."
            ) from None
        repository = GraphRepository(config)
        print("Connecting to investigation memory…", file=sys.stderr)
        if args.operation == "bootstrap":
            result = repository.ensure_schema()
            message = "Investigation memory is ready."
        elif args.operation == "record":
            print("Saving case context…", file=sys.stderr)
            result = repository.record_seed_context(args.evidence_id)
            message = "Case context saved."
        elif args.operation == "inspect":
            result = repository.get_investigation_context(args.evidence_id)
            message = "Saved investigation retrieved."
        else:
            result = repository.get_fingerprint_history(
                args.fingerprint, limit=args.limit
            )
            message = (
                "Related evidence retrieved."
                if result.candidates
                else "No related investigation evidence yet."
            )
        print(encode(result.model_dump()).decode())
        print(message, file=sys.stderr)
        return 0
    except KeyboardInterrupt:
        print(
            "Saving was interrupted. Retry with the same evidence ID to check completion.",
            file=sys.stderr,
        )
        return 130
    except ContextError as error:
        print(str(error), file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError, RecursionError):
        print(
            "Saved context could not be verified. Check the setup instructions and original evidence.",
            file=sys.stderr,
        )
        return 1
    finally:
        if repository:
            repository.close()


if __name__ == "__main__":
    sys.exit(main())
