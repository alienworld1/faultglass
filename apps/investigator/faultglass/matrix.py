from importlib.resources import files

from .jsonio import loads
from .models import EnginePair, EngineSpec

CONFIG = loads(files("faultglass").joinpath("engine-matrix.json").read_bytes())
PLATFORM = CONFIG["platform"]
ENGINES = [EngineSpec.model_validate(value) for value in CONFIG["engines"]]
PAIRS = [EnginePair.model_validate(value) for value in CONFIG["pairs"]]
if len({engine.id for engine in ENGINES}) != len(ENGINES) or len(
    {pair.id for pair in PAIRS}
) != len(PAIRS):
    raise ValueError("Curated engine identities must be unique.")


def engines_for(pair_id):
    if not PAIRS:
        raise ValueError("No verified engine pair is available.")
    pair = next((pair for pair in PAIRS if pair.id == pair_id), None)
    if pair is None:
        raise ValueError("Choose an available engine pair.")
    by_id = {engine.id: engine for engine in ENGINES}
    return by_id[pair.baselineId], by_id[pair.targetId]


for pair in PAIRS:
    engines_for(pair.id)
