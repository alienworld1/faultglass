import time
from typing import Protocol

import docker
from docker.errors import DockerException
from redis.exceptions import ResponseError

from .adapter import classify_error, query
from .errors import DeadlineExceeded, ExecutionFailure
from .inputs import executable_envelope
from .jsonio import digest
from .lifecycle import cleanup_deadline, finish_cleanup_before_interrupt
from .matrix import PLATFORM
from .models import (
    CheckObservation,
    EngineError,
    EngineObservation,
    PairedObservation,
    Timing,
)
from .runner_profile import PROFILE
from .transport import ExecTransport

OWNER = "faultglass.run"


class Runner(Protocol):
    def execute_pair(self, case, baseline, target, limits) -> PairedObservation: ...


def docker_client(timeout=5):
    return docker.from_env(timeout=timeout)


def verify_images(client, engines):
    info = client.info()
    if info.get("OSType") != "linux" or info.get("Architecture") not in (
        "x86_64",
        "amd64",
    ):
        raise ExecutionFailure(
            "platform",
            "preflight",
            "Use a Linux/amd64 Docker engine for this approved pair.",
        )
    images = []
    for engine in engines:
        try:
            image = client.images.get(engine.imageRef)
        except DockerException as error:
            raise ExecutionFailure(
                "image_unavailable",
                "preflight",
                "The selected engine image isn't ready. Prepare the approved image and try again.",
            ) from error
        references = image.attrs.get("RepoDigests", [])
        if (
            not any(
                reference.endswith("@" + engine.imageDigest) for reference in references
            )
            or image.attrs.get("Architecture") != "amd64"
            or image.attrs.get("Os") != "linux"
        ):
            raise ExecutionFailure(
                "image_mismatch",
                "preflight",
                "The selected engine image does not match its approved digest and platform.",
            )
        images.append(image)
    return images


class DockerRunner:
    def __init__(self, client, run_id):
        self.client, self.run_id = client, run_id
        self.containers = []
        self.evidence = {}
        self.deadline = 0.0

    def create(self, engine, role, limits):
        if time.monotonic() >= self.deadline:
            raise ExecutionFailure(
                "pair_deadline",
                "provisioning",
                "The paired comparison exceeded its time limit.",
                role,
            )
        container = self.client.containers.create(
            engine.imageRef,
            entrypoint="redis-server",
            command=[
                "--bind",
                "127.0.0.1",
                "--save",
                "",
                "--appendonly",
                "no",
                "--dir",
                "/tmp",
                "--loadmodule",
                "/var/lib/falkordb/bin/falkordb.so",
                "THREAD_COUNT",
                "2",
                "OMP_THREAD_COUNT",
                "1",
                "RESULTSET_SIZE",
                str(limits.rows + 1),
            ],
            network_mode="none",
            read_only=True,
            tmpfs={"/tmp": "rw,noexec,nosuid,size=134217728,mode=1777"},
            nano_cpus=1000000000,
            mem_limit=536870912,
            memswap_limit=536870912,
            pids_limit=128,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            user="65534:65534",
            environment=PROFILE["environment"],
            labels={OWNER: self.run_id, "faultglass.role": role},
            restart_policy={"Name": "no"},
            log_config=docker.types.LogConfig(
                type="local",
                config={"max-size": "256k", "max-file": "1", "compress": "false"},
            ),
            platform=PLATFORM,
        )
        self.containers.append(container)
        self.evidence[role] = {
            "role": role,
            "ownershipLabel": self.run_id,
            "containerId": container.id,
            "engine": engine.model_dump(),
            "platform": PLATFORM,
            "imageId": container.image.id,
            "stage": "startup",
            "limits": limits.model_dump(),
            "profile": PROFILE,
            "cleanup": "pending",
            "raw": [],
        }
        container.start()
        container.reload()
        config = container.attrs["HostConfig"]
        if (
            config["NetworkMode"] != "none"
            or config.get("Binds")
            or config.get("Privileged")
            or config.get("PortBindings")
            or not config["ReadonlyRootfs"]
            or config["Memory"] != PROFILE["memoryBytes"]
            or config["NanoCpus"] != 1000000000
            or config["PidsLimit"] != 128
            or config["MemorySwap"] != PROFILE["memoryBytes"]
            or config.get("Tmpfs")
            != {"/tmp": "rw,noexec,nosuid,size=134217728,mode=1777"}
            or config.get("CapDrop") != ["ALL"]
            or config.get("SecurityOpt") != ["no-new-privileges:true"]
            or config.get("RestartPolicy", {}).get("Name") != "no"
            or container.attrs["Config"].get("User") != PROFILE["user"]
            or container.attrs.get("Mounts")
        ):
            raise ExecutionFailure(
                "sandbox",
                "startup",
                "The engine isolation profile could not be established.",
                role,
            )
        self.evidence[role]["runtimeProfile"] = {
            key: config.get(key)
            for key in (
                "NetworkMode",
                "Binds",
                "PortBindings",
                "ReadonlyRootfs",
                "Memory",
                "MemorySwap",
                "NanoCpus",
                "PidsLimit",
                "Tmpfs",
                "CapDrop",
                "SecurityOpt",
                "RestartPolicy",
            )
        }
        return container

    def ready(self, transport, container, limits):
        deadline = min(self.deadline, time.monotonic() + limits.startupSeconds)
        while time.monotonic() < deadline:
            container.reload()
            if not container.attrs["State"]["Running"]:
                break
            try:
                if (
                    transport.command(
                        "PING", seconds=min(1.0, max(0.01, deadline - time.monotonic()))
                    )
                    == "PONG"
                ):
                    return
            except (ExecutionFailure, DeadlineExceeded, ValueError):
                time.sleep(0.05)
        raise ExecutionFailure(
            "startup",
            "startup",
            "The engine did not become ready. Check the approved image and Docker resources.",
        )

    def outcome(self, container, action):
        try:
            value = action()
            container.reload()
            if not container.attrs["State"]["Running"]:
                return (
                    "crash",
                    None,
                    EngineError(
                        category="CRASH", detail="The engine stopped during execution."
                    ),
                )
            return "result", value, None
        except (
            ResponseError,
            DeadlineExceeded,
            ExecutionFailure,
            DockerException,
        ) as error:
            health_deadline = min(self.deadline, time.monotonic() + 1.0)
            while True:
                container.reload()
                state = container.attrs["State"]
                if (
                    not state["Running"]
                    or not isinstance(error, (ExecutionFailure, DockerException))
                    or time.monotonic() >= health_deadline
                ):
                    break
                time.sleep(0.02)
            if not state["Running"]:
                return (
                    "crash",
                    None,
                    EngineError(
                        category="CRASH", detail="The engine stopped during execution."
                    ),
                )
            if isinstance(error, DeadlineExceeded):
                return (
                    "timeout",
                    None,
                    EngineError(
                        category="TIMEOUT", detail="The query exceeded its time limit."
                    ),
                )
            if isinstance(error, ResponseError):
                return "error", None, classify_error(str(error))
            raise

    def execute_engine(self, case, engine, role, limits):
        container = self.create(engine, role, limits)
        transport = ExecTransport(self.client, container, limits, self.deadline)
        metadata = self.evidence[role]
        metadata["executableInputDigest"] = digest(executable_envelope(case, limits))
        metadata["raw"] = transport.raw
        started = time.monotonic()
        self.ready(transport, container, limits)
        graph = transport.graph()
        ordered = case.observation.ordering == "ordered"
        for index, text in enumerate(case.setup):
            metadata["stage"] = "setup"
            metadata["setupIndex"] = index
            try:
                query(graph, transport, text, {}, ordered, limits)
            except (
                ResponseError,
                DeadlineExceeded,
                ExecutionFailure,
                ValueError,
            ) as error:
                raise ExecutionFailure(
                    "setup",
                    "setup",
                    "The fixture could not be prepared. Inspect the saved engine evidence.",
                    role,
                ) from error
        metadata["stage"] = "focal"
        status, value, error = self.outcome(
            container,
            lambda: query(
                graph, transport, case.query, case.parameters, ordered, limits
            ),
        )
        checks, skipped = [], []
        for check in case.observation.postconditions:
            if status in ("crash", "timeout"):
                skipped.append({"name": check.name, "reason": status})
                continue
            container.reload()
            if not container.attrs["State"]["Running"]:
                skipped.append({"name": check.name, "reason": "engine_stopped"})
                continue
            metadata["stage"] = "postcondition"
            check_status, check_value, check_error = self.outcome(
                container,
                lambda check=check: query(
                    graph,
                    transport,
                    check.query,
                    check.parameters,
                    ordered,
                    limits,
                    read_only=True,
                ),
            )
            checks.append(
                CheckObservation(
                    name=check.name,
                    status="result" if check_status == "result" else "error",
                    value=check_value or check_error,
                )
            )
            if check_status == "timeout":
                skipped.extend(
                    {"name": remaining.name, "reason": "postcondition_timeout"}
                    for remaining in case.observation.postconditions[len(checks) :]
                )
                break
        metadata["skippedPostconditions"] = skipped
        container.reload()
        metadata["exitState"] = {
            key: container.attrs["State"].get(key)
            for key in ("Running", "ExitCode", "OOMKilled", "Error")
        }
        metadata["stage"] = "observed"
        return EngineObservation(
            engineVersionId=engine.id,
            status=status,
            result=value,
            error=error,
            postconditions=checks,
            timing=Timing(durationMs=(time.monotonic() - started) * 1000),
        )

    def cleanup(self, limits):
        with finish_cleanup_before_interrupt():
            self.cleanup_owned(limits)

    def cleanup_owned(self, limits):
        failures = []
        previous_timeout = self.client.api.timeout
        self.client.api.timeout = min(5, limits.cleanupSeconds / 2)
        try:
            owned = self.client.containers.list(
                all=True, filters={"label": f"{OWNER}={self.run_id}"}
            )
            known = {container.id for container in self.containers}
            self.containers.extend(
                container for container in owned if container.id not in known
            )
        except DockerException:
            failures.append("ownership_lookup")
        for container in self.containers:
            role = (
                container.attrs.get("Config", {})
                .get("Labels", {})
                .get("faultglass.role")
            )
            metadata = self.evidence.get(role, {})
            try:
                with cleanup_deadline(limits.cleanupSeconds):
                    self.capture_logs(container, metadata, limits)
                    container.remove(force=True, v=True)
                metadata["cleanup"] = "removed"
            except (DockerException, DeadlineExceeded):
                metadata["cleanup"] = "incomplete"
                failures.append(container.id)
        self.client.api.timeout = previous_timeout
        if failures:
            raise ExecutionFailure(
                "cleanup",
                "cleanup",
                "Owned engines could not be removed. Use the recovery command before running again.",
            )

    def capture_logs(self, container, metadata, limits):
        try:
            logs = bytearray()
            truncated = False
            for chunk in container.logs(stream=True, follow=False, tail="all"):
                if len(logs) + len(chunk) > limits.logBytes:
                    logs.extend(chunk[: max(0, limits.logBytes - len(logs))])
                    truncated = True
                    break
                logs.extend(chunk)
            metadata["logs"] = logs.decode(errors="replace")
            metadata["logsTruncated"] = truncated
            metadata["logRetentionBytes"] = 262144
        except DockerException:
            metadata["logsUnavailable"] = True

    def execute_pair(self, case, baseline, target, limits):
        self.deadline = time.monotonic() + limits.pairSeconds
        try:
            left = self.execute_engine(case, baseline, "baseline", limits)
            right = self.execute_engine(case, target, "target", limits)
            if time.monotonic() > self.deadline:
                raise ExecutionFailure(
                    "pair_deadline",
                    "comparison",
                    "The paired comparison exceeded its time limit.",
                )
            return PairedObservation(baseline=left, target=right)
        finally:
            self.cleanup(limits)
