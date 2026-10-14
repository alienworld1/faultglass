import hashlib
import json


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Use unique JSON field names.")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Use finite JSON numbers.")


def loads(data):
    return json.loads(
        data, object_pairs_hook=unique_object, parse_constant=reject_constant
    )


def encode(value):
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode()


def digest(value):
    return hashlib.sha256(encode(value)).hexdigest()
