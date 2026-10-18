import argparse
import os
import platform
import sys
from contextlib import closing
from uuid import uuid4

from docker.errors import DockerException

from .artifacts import open_private_root
from .context_config import ContextConfig
from .context_errors import ContextError
from .context_lock import ContextLease
from .errors import ExecutionFailure
from .gemini import agent_readiness
from .graph_repository import GraphRepository
from .matrix import PAIRS, engines_for
from .probe_graph import catalog
from .runner import docker_client, verify_images
from .storage_policy import storage_issue


def check(*, bootstrap=False, worker=False):
    issues = []
    if platform.system() != "Linux" or platform.machine() not in {"x86_64", "amd64"}:
        issues.append("Use a Linux/amd64 host.")
    config = ContextConfig.from_environment()
    if not config.artifact_root.is_absolute():
        issues.append("Set one absolute evidence root for the API and worker.")
    storage = storage_issue(config.artifact_root)
    if storage:
        issues.append("Check evidence storage: " + storage + ".")
    try:
        _, fd = open_private_root(config.artifact_root)
        name = ".preflight-" + uuid4().hex
        try:
            probe = os.open(
                name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600, dir_fd=fd
            )
            try:
                os.write(probe, b"storage check")
                os.fsync(probe)
            finally:
                os.close(probe)
                os.unlink(name, dir_fd=fd)
            os.fsync(fd)
        finally:
            os.close(fd)
    except (OSError, ValueError):
        issues.append("Make the evidence root writable by the service account.")
    try:
        with closing(docker_client()) as client:
            for pair in PAIRS:
                verify_images(client, engines_for(pair.id))
    except (DockerException, ExecutionFailure, OSError):
        issues.append("Check Docker access and acquire the exact approved images.")
    try:
        with closing(GraphRepository(config)) as repository:
            if bootstrap and not issues:
                repository.ensure_schema()
                with ContextLease():
                    catalog(repository, bootstrap=True)
            else:
                repository._assert_ready()
                catalog(repository)
    except (ContextError, OSError, ValueError):
        issues.append(
            "Check persistent context, timeout settings, indexes and catalog."
        )
    origins = os.environ.get("FAULTGLASS_ALLOWED_ORIGINS", "")
    from .investigation_api import mutation_origins

    if not origins or any(
        not origin.startswith(("https://", "http://127.0.0.1:", "http://localhost:"))
        or origin.endswith("/")
        or "*" in origin
        for origin in mutation_origins()
    ):
        issues.append(
            "Set explicit trusted origins without trailing slashes or wildcards."
        )
    if worker:
        ready = agent_readiness()
        if (
            not ready["agentReady"]
            and ready["agentReason"] != "deterministic_diagnostic"
        ):
            issues.append(
                "Check worker provider configuration: " + ready["agentReason"] + "."
            )
    elif os.environ.get("GEMINI_API_KEY"):
        issues.append("Remove the provider key from the API environment.")
    return issues


def main():
    parser = argparse.ArgumentParser(
        description="Check trusted investigation dependencies."
    )
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    try:
        issues = check(bootstrap=args.bootstrap, worker=args.worker)
    except (OSError, ValueError, ContextError):
        issues = ["Check trusted environment configuration and service permissions."]
    for issue in issues:
        print(issue, file=sys.stderr)
    if not issues:
        print(
            "Dependencies verified. Provider access and quota require a live investigation."
        )
    return int(bool(issues))


if __name__ == "__main__":
    sys.exit(main())
