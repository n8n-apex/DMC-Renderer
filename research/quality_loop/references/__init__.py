"""Reference library: index build + retrieval.

Exposes `retrieve_references(st_type, axes, k=3)` which returns the top-k
reference rows of a given st_type, ranked by axis-distance to a query.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
INDEX_PATH = os.path.join(HERE, "index.json")


def _axis_distance(row_axes: dict, query_axes: dict) -> int:
    """Count of axis keys whose value differs between the row and the query.

    Lower = closer. Keys present in either dict are considered; a key missing
    on one side counts as a difference.
    """
    keys = set(row_axes) | set(query_axes)
    return sum(1 for key in keys if row_axes.get(key) != query_axes.get(key))


def retrieve_references(st_type: str, axes: dict, k: int = 3, index_path: str = INDEX_PATH) -> list[dict]:
    """Return up to `k` reference rows matching `st_type`, sorted by axis-distance.

    - load index.json
    - keep rows whose st_type == st_type
    - sort ascending by axis-distance (count of differing axis keys)
    - return the top k full row dicts
    """
    with open(index_path) as f:
        rows = json.load(f)

    matching = [r for r in rows if r.get("st_type") == st_type]
    matching.sort(key=lambda r: (_axis_distance(r.get("axes", {}), axes), r.get("page_no", 0)))
    return matching[:k]
