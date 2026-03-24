"""Explicit multi-role **simulation** of the qhpc_cache research workflow.

This is **not** an LLM agent framework. It models named research roles, tasks,
and events so traces can be exported as JSON/JSONL/text via
``research_workflow_export`` (optional teaching / audit path — **not** the core
research spine).

No external agent runtime is invoked from this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid


@dataclass
class ResearchAgentProfile:
    """A modeled research contributor (human or tool-assisted), not a running bot."""

    agent_name: str
    agent_role: str
    agent_description: str
    assigned_directory: str
    assigned_focus_area: str
    preferred_tools: List[str]
    current_status: str = "idle"


@dataclass
class ResearchTask:
    """Unit of work tied to this repository and literature labels."""

    task_identifier: str
    task_title: str
    task_description: str
    related_module_names: List[str]
    related_paper_labels: List[str]
    task_priority: str
    task_stage: str
    task_notes: str = ""


@dataclass
class ResearchTaskEvent:
    """Single timestamped activity in the simulated workflow."""

    event_identifier: str
    agent_name: str
    event_type: str
    event_timestamp: str
    task_identifier: str
    active_file_path: str
    event_summary: str
    event_details: str
    status_label: str


@dataclass
class ResearchWorkflowState:
    """Snapshot of queue/completion at a point in time."""

    workflow_name: str
    active_agents: List[str]
    queued_tasks: List[str]
    completed_tasks: List[str]
    active_events: List[str]
    notes: str = ""


@dataclass
class ResearchSimulationTrace:
    """Full run of the simulation: snapshots + flat event log + provenance."""

    trace_name: str
    workflow_state_snapshots: List[ResearchWorkflowState]
    event_log: List[ResearchTaskEvent]
    generated_from: str


def build_default_research_agent_profiles() -> List[ResearchAgentProfile]:
    """Seven roles aligned with qhpc_cache layers and research support."""
    base = "jk/src/qhpc_cache"
    return [
        ResearchAgentProfile(
            agent_name="FinanceModelAgent",
            agent_role="classical_pricing",
            agent_description="GBM, payoffs, Monte Carlo pricer, Black–Scholes checks.",
            assigned_directory=base,
            assigned_focus_area="pricing.py, market_models.py, payoffs.py, analytic_pricing.py",
            preferred_tools=["pytest", "run_demo.py", "black_scholes_call_price"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="RiskMetricsAgent",
            agent_role="risk_and_portfolio",
            agent_description="Sample VaR/CVaR, portfolio scenario P&L.",
            assigned_directory=base,
            assigned_focus_area="risk_metrics.py, portfolio.py",
            preferred_tools=["unittest", "compute_value_at_risk"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="QuantumMappingAgent",
            agent_role="quantum_planning",
            agent_description="Descriptors and placeholder resource estimates for QMCI / AE framing.",
            assigned_directory=base,
            assigned_focus_area="quantum_mapping.py, quantum_workflow.py",
            preferred_tools=["run_quantum_mapping_workflow", "docs"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="CachePolicyAgent",
            agent_role="cache_and_similarity",
            agent_description="Heuristic/logistic policies, circuit cache keys, similarity scores.",
            assigned_directory=base,
            assigned_focus_area="cache_policy.py, cache_store.py, circuit_similarity.py, circuit_cache.py",
            preferred_tools=["experiment_runner", "SimpleCacheStore"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="LiteratureReviewAgent",
            agent_role="paper_to_code",
            agent_description="Maps papers and survey ideas to modules and experiments.",
            assigned_directory="jk/docs",
            assigned_focus_area="research_to_code_mapping.md, finance_baseline_architecture.md",
            preferred_tools=["local arXiv tools", "PDF notes"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="ExperimentAgent",
            agent_role="batch_studies",
            agent_description="Replications, payoff comparisons, portfolio risk experiments.",
            assigned_directory=base,
            assigned_focus_area="experiment_runner.py, experiment_configs.py, reporting.py",
            preferred_tools=["run_monte_carlo_study", "run_payoff_comparison_experiment"],
            current_status="idle",
        ),
        ResearchAgentProfile(
            agent_name="VisualizationAgent",
            agent_role="workflow_visibility",
            agent_description="Exports matplotlib/seaborn figures and optional workflow JSON traces.",
            assigned_directory="jk/src/qhpc_cache/visualization",
            assigned_focus_area="plot_utils, research_workflow_export, markdown/CSV reports",
            preferred_tools=["export_research_trace_to_json", "jsonl"],
            current_status="idle",
        ),
    ]


def build_default_research_task_set() -> List[ResearchTask]:
    """Tasks grounded in actual modules and cited research themes (labels, not DOIs)."""
    return [
        ResearchTask(
            task_identifier="task-finance-mc-001",
            task_title="Monte Carlo baseline parity with Black–Scholes",
            task_description="Validate european_call MC against analytic_pricing; document SE and CI.",
            related_module_names=["pricing.py", "analytic_pricing.py", "variance_reduction.py"],
            related_paper_labels=["COS/Fourier pricing", "finance baseline / risk metrics"],
            task_priority="high",
            task_stage="in_progress",
            task_notes="Cross-check with fourier_placeholder.py COS benchmark.",
        ),
        ResearchTask(
            task_identifier="task-risk-002",
            task_title="Portfolio scenario VaR/CVaR teaching path",
            task_description="Keep analytic repricing vs MC PV split explicit in docs and demo.",
            related_module_names=["portfolio.py", "risk_metrics.py", "run_demo.py"],
            related_paper_labels=["sample quantile VaR (historical simulation style)"],
            task_priority="medium",
            task_stage="queued",
            task_notes="Undergraduate-friendly sign conventions in risk_metrics.",
        ),
        ResearchTask(
            task_identifier="task-quantum-003",
            task_title="Modular QMCI problem framing",
            task_description="Maintain honest placeholders on QuantumResourceEstimate; link to pricer.",
            related_module_names=["quantum_mapping.py", "quantum_workflow.py"],
            related_paper_labels=["modular QMCI ideas", "An et al. 2021"],
            task_priority="medium",
            task_stage="planning",
            task_notes="No device execution in qhpc_cache.",
        ),
        ResearchTask(
            task_identifier="task-cache-004",
            task_title="Circuit similarity and reuse narrative",
            task_description="Explainable similarity scores for circuit requests; connect to cache policy features.",
            related_module_names=["circuit_similarity.py", "circuit_cache.py", "cache_policy_features.py"],
            related_paper_labels=["similarity caching theory", "Moflic circuit caches"],
            task_priority="medium",
            task_stage="planning",
            task_notes="Research scaffold only.",
        ),
        ResearchTask(
            task_identifier="task-cache-policy-005",
            task_title="Policy comparison experiments",
            task_description="Heuristic vs logistic hit rates on synthetic feature streams.",
            related_module_names=["cache_policy.py", "experiment_runner.py"],
            related_paper_labels=["Herman 2023"],
            task_priority="low",
            task_stage="queued",
            task_notes="AIAssistedCachePolicy remains placeholder scorer.",
        ),
        ResearchTask(
            task_identifier="task-docs-006",
            task_title="Paper-to-code traceability",
            task_description="Refresh research_to_code_mapping and README tables after code changes.",
            related_module_names=["README.md", "docs/research_to_code_mapping.md"],
            related_paper_labels=["literature review", "QMCI surveys"],
            task_priority="medium",
            task_stage="ongoing",
            task_notes="LiteratureReviewAgent owns cross-links.",
        ),
    ]


def create_research_task_event(
    *,
    agent_name: str,
    event_type: str,
    task_identifier: str,
    active_file_path: str,
    event_summary: str,
    event_details: str = "",
    status_label: str = "active",
    event_timestamp: Optional[str] = None,
    event_identifier: Optional[str] = None,
) -> ResearchTaskEvent:
    """Factory for a single event (UTC ISO timestamp if none passed)."""
    ts = event_timestamp or datetime.now(timezone.utc).isoformat()
    eid = event_identifier or str(uuid.uuid4())
    return ResearchTaskEvent(
        event_identifier=eid,
        agent_name=agent_name,
        event_type=event_type,
        event_timestamp=ts,
        task_identifier=task_identifier,
        active_file_path=active_file_path,
        event_summary=event_summary,
        event_details=event_details,
        status_label=status_label,
    )


def summarize_research_workflow_state(state: ResearchWorkflowState) -> str:
    """Plain-text summary for console or markdown sidecars."""
    lines = [
        f"Workflow: {state.workflow_name}",
        f"Active agents ({len(state.active_agents)}): {', '.join(state.active_agents) or '—'}",
        f"Queued tasks ({len(state.queued_tasks)}): {', '.join(state.queued_tasks) or '—'}",
        f"Completed tasks ({len(state.completed_tasks)}): {', '.join(state.completed_tasks) or '—'}",
        f"Recent event ids ({len(state.active_events)}): {', '.join(state.active_events) or '—'}",
    ]
    if state.notes:
        lines.append(f"Notes: {state.notes}")
    return "\n".join(lines)


def _dataclass_to_dict(obj: Any) -> Dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        return {k: _dataclass_to_dict(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, list):
        return [_dataclass_to_dict(item) for item in obj]
    return obj


def simulation_trace_to_serializable(trace: ResearchSimulationTrace) -> Dict[str, Any]:
    """Convert trace to JSON-serializable dict (for export helpers)."""
    return {
        "trace_name": trace.trace_name,
        "generated_from": trace.generated_from,
        "workflow_state_snapshots": _dataclass_to_dict(trace.workflow_state_snapshots),
        "event_log": _dataclass_to_dict(trace.event_log),
    }


def build_demo_simulation_trace() -> ResearchSimulationTrace:
    """Construct a short, realistic timeline for demos and tests."""
    agents = build_default_research_agent_profiles()
    tasks = build_default_research_task_set()

    events: List[ResearchTaskEvent] = []
    snapshots: List[ResearchWorkflowState] = []

    def add_event(
        agent_name: str,
        etype: str,
        tid: str,
        path: str,
        summary: str,
        *,
        status_label: str = "active",
    ) -> None:
        events.append(
            create_research_task_event(
                agent_name=agent_name,
                event_type=etype,
                task_identifier=tid,
                active_file_path=path,
                event_summary=summary,
                status_label=status_label,
            )
        )

    queued_ids = [t.task_identifier for t in tasks if t.task_stage == "queued"]

    snapshots.append(
        ResearchWorkflowState(
            workflow_name="qhpc_research_day_1",
            active_agents=[a.agent_name for a in agents[:3]],
            queued_tasks=queued_ids,
            completed_tasks=[],
            active_events=[],
            notes="Kickoff: finance + risk + quantum planning.",
        )
    )

    add_event(
        "FinanceModelAgent",
        "tool_simulation",
        "task-finance-mc-001",
        "jk/src/qhpc_cache/pricing.py",
        "Reviewed terminal GBM loop and antithetic branch",
    )
    add_event(
        "RiskMetricsAgent",
        "tool_simulation",
        "task-risk-002",
        "jk/src/qhpc_cache/risk_metrics.py",
        "Verified VaR/CVaR sample quantile docstrings",
    )
    add_event(
        "QuantumMappingAgent",
        "planning",
        "task-quantum-003",
        "jk/src/qhpc_cache/quantum_mapping.py",
        "Confirmed placeholder labels on QuantumResourceEstimate",
    )

    snapshots.append(
        ResearchWorkflowState(
            workflow_name="qhpc_research_day_1",
            active_agents=[a.agent_name for a in agents],
            queued_tasks=["task-cache-policy-005", "task-risk-002"],
            completed_tasks=["task-finance-mc-001"],
            active_events=[events[-1].event_identifier],
            notes="Finance baseline check complete; cache policy queued.",
        )
    )

    add_event(
        "CachePolicyAgent",
        "experiment_design",
        "task-cache-004",
        "jk/src/qhpc_cache/circuit_similarity.py",
        "Sketched finance+circuit similarity breakdown strings",
    )
    add_event(
        "ExperimentAgent",
        "batch_run",
        "task-cache-policy-005",
        "jk/src/qhpc_cache/experiment_runner.py",
        "Defined run_payoff_comparison_experiment smoke path",
    )
    add_event(
        "LiteratureReviewAgent",
        "mapping",
        "task-docs-006",
        "jk/docs/research_to_code_mapping.md",
        "Linked modular QMCI and COS/Fourier rows to modules",
    )
    add_event(
        "VisualizationAgent",
        "export",
        "task-docs-006",
        "jk/src/qhpc_cache/research_workflow_export.py",
        "Prepared JSON + JSONL export for workflow trace",
        status_label="complete",
    )

    snapshots.append(
        ResearchWorkflowState(
            workflow_name="qhpc_research_day_1",
            active_agents=["VisualizationAgent", "LiteratureReviewAgent"],
            queued_tasks=["task-risk-002"],
            completed_tasks=[
                "task-finance-mc-001",
                "task-quantum-003",
                "task-cache-004",
                "task-cache-policy-005",
                "task-docs-006",
            ],
            active_events=[e.event_identifier for e in events[-2:]],
            notes="Trace export ready (in-package JSON/JSONL; no external bridge).",
        )
    )

    return ResearchSimulationTrace(
        trace_name="qhpc_cache_research_workflow_demo",
        workflow_state_snapshots=snapshots,
        event_log=events,
        generated_from="qhpc_cache.research_agents.build_demo_simulation_trace",
    )
