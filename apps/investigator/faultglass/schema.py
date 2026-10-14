import argparse
from pathlib import Path

from pydantic import create_model

from .jsonio import encode
from .models import Contract, EnginePair, EngineSpec, FaultCase, RunReport


def export_schema():
    envelope = create_model(
        "EvidenceContracts",
        __base__=Contract,
        case=(FaultCase, ...),
        engine=(EngineSpec, ...),
        pair=(EnginePair, ...),
        report=(RunReport, ...),
    )
    schema = envelope.model_json_schema()
    schema["$defs"]["JsonValue"] = {
        "anyOf": [
            {"type": "null"},
            {"type": "boolean"},
            {"type": "number"},
            {"type": "string"},
            {"type": "array", "items": {"$ref": "#/$defs/JsonValue"}},
            {"type": "object", "additionalProperties": {"$ref": "#/$defs/JsonValue"}},
        ]
    }
    return schema


def main():
    parser = argparse.ArgumentParser(
        description="Export the authoritative evidence contracts."
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.write_bytes(encode(export_schema()))


if __name__ == "__main__":
    main()
