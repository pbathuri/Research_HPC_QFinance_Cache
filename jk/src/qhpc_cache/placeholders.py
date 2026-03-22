"""**PLACEHOLDER** datatypes for future quantum circuit and metadata wiring.

Not used in classical pricing or risk results. Prefer ``circuit_cache`` and
``quantum_mapping`` for active research scaffolding.
"""

from dataclasses import dataclass


@dataclass
class CircuitFragmentPlaceholder:
    """Stub record for a circuit fragment (no execution backend attached)."""

    fragment_id: str
    fragment_type: str
    estimated_depth: int
    estimated_qubits: int


@dataclass
class CircuitMetadataPlaceholder:
    """Stub record for reuse/similarity metadata (future extension)."""

    reuse_count: int
    similarity_score: float
    compile_cost_estimate: float
