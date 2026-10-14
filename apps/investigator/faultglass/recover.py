import argparse
from contextlib import closing
from uuid import UUID

from .artifacts import Lease
from .runner import OWNER, docker_client


def main():
    parser = argparse.ArgumentParser(
        description="Remove engines owned by an interrupted comparison."
    )
    parser.add_argument("--run-id", required=True, type=UUID)
    args = parser.parse_args()
    with Lease(), closing(docker_client()) as client:
        containers = client.containers.list(
            all=True, filters={"label": f"{OWNER}={args.run_id}"}
        )
        for container in containers:
            container.remove(force=True, v=True)
        print(f"Removed {len(containers)} owned engines.")


if __name__ == "__main__":
    main()
