"""Build feature dicts for cache policy decisions."""


def build_cache_features(
    instrument_type: str,
    num_paths: int,
    volatility: float,
    maturity: float,
) -> dict:
    """Build a feature dict for cache policy input.

    Returns a dict with keys: instrument_type, num_paths, volatility, maturity.
    In future, circuit-level features can be added here (e.g. circuit_depth,
    qubit_count, fragment_reuse_count, similarity_score).
    """
    return {
        "instrument_type": instrument_type,
        "num_paths": num_paths,
        "volatility": volatility,
        "maturity": maturity,
    }


def build_future_circuit_features(
    fragment_depth: int,
    qubit_count: int,
    reuse_count: int,
    similarity_score: float,
) -> dict:
    """Build a feature dict for future circuit-level cache policy input.

    Not connected to active pricing logic yet. Returns a dict with
    fragment_depth, qubit_count, reuse_count, similarity_score.
    """
    return {
        "fragment_depth": fragment_depth,
        "qubit_count": qubit_count,
        "reuse_count": reuse_count,
        "similarity_score": similarity_score,
    }
