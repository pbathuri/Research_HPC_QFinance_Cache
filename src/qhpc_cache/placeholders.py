"""Placeholders for future quantum circuit representation and similarity-based caching."""

from dataclasses import dataclass


# Future stub: circuit representation and fragment-level caching.
@dataclass
class CircuitFragmentPlaceholder:
    """Placeholder for a quantum circuit fragment (future extension)."""

    fragment_id: str
    fragment_type: str
    estimated_depth: int
    estimated_qubits: int


# Future stub: circuit similarity scoring and compile-cost metadata.
@dataclass
class CircuitMetadataPlaceholder:
    """Placeholder for circuit metadata used in similarity and reuse (future extension)."""

    reuse_count: int
    similarity_score: float
    compile_cost_estimate: float
