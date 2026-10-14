import argparse
from pathlib import Path

from .artifacts import verify


def main():
    parser = argparse.ArgumentParser(description="Check a complete evidence receipt.")
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    try:
        count = verify(args.directory)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, "The evidence could not be verified: " + str(error) + "\n")
    print(f"Verified {count} evidence artifacts.")


if __name__ == "__main__":
    main()
