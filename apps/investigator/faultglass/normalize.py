import math
from collections.abc import Mapping

from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path

from .jsonio import encode
from .models import Result

VERSION = "typed-values-v1"


def normalize(value):
    if value is None:
        return {"kind": "null"}
    if type(value) is bool:
        return {"kind": "boolean", "value": value}
    if type(value) is int:
        return {"kind": "integer", "value": str(value)}
    if type(value) is float:
        if not math.isfinite(value):
            raise ValueError("Non-finite engine numbers cannot be compared.")
        return {"kind": "float", "value": value.hex()}
    if type(value) is str:
        return {"kind": "string", "value": value}
    if isinstance(value, Path):
        nodes, edges = value.nodes(), value.edges()
        if len(nodes) != len(edges) + 1:
            raise ValueError("Ambiguous path structure cannot be compared.")
        directions = []
        for i, edge in enumerate(edges):
            forward = edge.src_node == nodes[i].id and edge.dest_node == nodes[i + 1].id
            reverse = edge.dest_node == nodes[i].id and edge.src_node == nodes[i + 1].id
            if forward == reverse:
                raise ValueError("Ambiguous path direction cannot be compared.")
            directions.append("forward" if forward else "reverse")
        return {
            "kind": "path",
            "nodes": [normalize(n) for n in nodes],
            "relationships": [normalize(e) for e in edges],
            "directions": directions,
        }
    if isinstance(value, Node):
        return {
            "kind": "node",
            "labels": sorted(value.labels or []),
            "properties": normalize(value.properties),
        }
    if isinstance(value, Edge):
        return {
            "kind": "relationship",
            "type": value.relation,
            "properties": normalize(value.properties),
        }
    if isinstance(value, Mapping):
        if any(type(key) is not str for key in value):
            raise ValueError("Engine map keys must be strings.")
        return {
            "kind": "map",
            "value": {key: normalize(value[key]) for key in sorted(value)},
        }
    if type(value) is list:
        return {"kind": "list", "value": [normalize(item) for item in value]}
    raise ValueError("This engine value is not supported for complete comparison.")


def result(columns, rows, ordered, limits):
    if len(rows) > limits.rows or any(len(row) != len(columns) for row in rows):
        raise ValueError(
            "The output exceeded the comparison limit or has incomplete rows."
        )
    value = Result(
        columns=columns,
        rows=[[normalize(cell) for cell in row] for row in rows],
        ordered=ordered,
    )
    if len(encode(value.model_dump())) > limits.outputBytes:
        raise ValueError("The output exceeded the comparison limit.")
    return value
