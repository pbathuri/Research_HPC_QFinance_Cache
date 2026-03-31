"""Slurm / BigRed200 backend: submission artifact generation (no remote submit).

This backend generates reproducible ``sbatch`` scripts and job manifests that can
be staged and submitted on BigRed200. It does not submit jobs from local Macs.
"""

from __future__ import annotations

import textwrap
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
from typing import Any, Dict

from qhpc_cache.backends.base import (
    BackendCapabilities,
    BaseBackend,
    ExecutionPlan,
    SlurmResourceSpec,
)


_SBATCH_TEMPLATE = textwrap.dedent("""\
    #!/bin/bash
    #SBATCH --job-name={job_name}
    #SBATCH --partition={partition}
    #SBATCH --nodes={nodes}
    #SBATCH --ntasks={ntasks}
    #SBATCH --cpus-per-task={cpus_per_task}
    #SBATCH --time={walltime}
    #SBATCH --mem={mem}
    #SBATCH --output={output_log}
    #SBATCH --error={error_log}
{optional_headers}

    module load python/3.11
{module_lines}

    cd $SLURM_SUBMIT_DIR
    {launch_prefix}{run_command}
""")


class SlurmBigRed200Backend(BaseBackend):

    def capabilities(self) -> BackendCapabilities:
        return BackendCapabilities(
            name="slurm_bigred200",
            backend_kind="hpc_slurm",
            execution_environment="hpc",
            execution_mode_intent="cpu_batch_slurm",
            can_execute=True,
            supports_mpi=True,
            supports_batch_scheduler=True,
            hpc_ready=True,
            mpi_ready=True,
            gpu_ready=False,
            max_parallel_paths=0,
            notes="Generates BigRed200 sbatch + manifest artifacts; remote submission is manual.",
        )

    def validate(self) -> bool:
        return True

    def build_plan(self, task_type: str, params: Dict[str, Any], *, dry_run: bool = False) -> ExecutionPlan:
        num_paths = int(params.get("num_paths", 1_000_000))
        nodes = int(params.get("slurm_nodes", params.get("nodes", 1)))
        ntasks = int(params.get("slurm_ntasks", params.get("ntasks", max(1, nodes))))
        cpus_per_task = int(params.get("slurm_cpus_per_task", params.get("cpus_per_task", 1)))
        partition = str(params.get("slurm_partition", params.get("partition", "general")))
        walltime = str(params.get("slurm_walltime", params.get("time_limit", "01:00:00")))
        mem = str(params.get("slurm_mem", params.get("mem", "16G")))
        job_name = str(params.get("slurm_job_name", f"qhpc_{task_type}"))
        output_log = str(params.get("slurm_output_log", "slurm_%j.out"))
        error_log = str(params.get("slurm_error_log", "slurm_%j.err"))
        account = str(params.get("slurm_account", ""))
        constraint = str(params.get("slurm_constraint", ""))
        qos = str(params.get("slurm_qos", ""))
        exec_mode_intent = str(params.get("execution_mode_intent", "cpu_batch_slurm"))

        slurm_spec = SlurmResourceSpec(
            job_name=job_name,
            walltime=walltime,
            partition=partition,
            nodes=nodes,
            ntasks=ntasks,
            cpus_per_task=cpus_per_task,
            mem=mem,
            output_log=output_log,
            error_log=error_log,
            account=account,
            constraint=constraint,
            qos=qos,
        )
        return ExecutionPlan(
            plan_id=str(params.get("plan_id", f"slurm_{task_type}_{nodes}n_{ntasks}t")),
            backend_name="slurm_bigred200",
            task_type=task_type,
            requested_backend=str(params.get("requested_backend", "slurm_bigred200")),
            execution_environment_intent="hpc",
            execution_mode_intent=exec_mode_intent,
            execution_mode_actual="slurm_submission_artifacts_only",
            parameters={
                **params,
                "num_paths": num_paths,
                "slurm_nodes": nodes,
                "slurm_ntasks": ntasks,
                "slurm_cpus_per_task": cpus_per_task,
                "slurm_partition": partition,
                "slurm_walltime": walltime,
                "slurm_mem": mem,
                "slurm_job_name": job_name,
                "slurm_output_log": output_log,
                "slurm_error_log": error_log,
            },
            estimated_runtime_seconds=max(1.0, num_paths / max(1, ntasks * cpus_per_task * 500_000)),
            estimated_memory_bytes=num_paths * 64,
            dry_run=dry_run,
            slurm=slurm_spec,
            notes=f"BigRed200 Slurm plan: nodes={nodes}, ntasks={ntasks}, cpus_per_task={cpus_per_task}.",
        )

    def execute(self, plan: ExecutionPlan) -> Dict[str, Any]:
        script = self._render_sbatch(plan)
        artifact_dir = plan.parameters.get("artifact_dir")
        script_path = ""
        manifest_path = ""
        if artifact_dir:
            artifact_paths = self._materialize_artifacts(plan, script, Path(str(artifact_dir)))
            script_path = artifact_paths["sbatch_script_path"]
            manifest_path = artifact_paths["slurm_job_manifest_path"]
        return {
            "status": "template_generated",
            "backend": "slurm_bigred200",
            "sbatch_script": script,
            "sbatch_script_path": script_path,
            "slurm_job_manifest_path": manifest_path,
            "workload_to_slurm_mapping_csv": artifact_paths.get("workload_to_slurm_mapping_csv", "") if artifact_dir else "",
            "backend_readiness_md": artifact_paths.get("backend_readiness_md", "") if artifact_dir else "",
            "message": "Submission artifacts generated locally. Submit on BigRed200 with: sbatch <script.sh>",
        }

    def dry_run_summary(self, plan: ExecutionPlan) -> str:
        p = plan.parameters
        return (
            f"[slurm_bigred200] task={plan.task_type}  "
            f"paths={p.get('num_paths', '?')}  "
            f"nodes={p.get('slurm_nodes', 1)} ntasks={p.get('slurm_ntasks', 1)} cpus/task={p.get('slurm_cpus_per_task', 1)}  "
            f"mode={plan.execution_mode_intent}  "
            f"will generate BigRed200 submission artifacts."
        )

    def _render_sbatch(self, plan: ExecutionPlan) -> str:
        p = dict(plan.parameters)
        spec = plan.slurm or SlurmResourceSpec()
        account = str(spec.account).strip()
        constraint = str(spec.constraint).strip()
        qos = str(spec.qos).strip()
        optional_headers = []
        if account:
            optional_headers.append(f"#SBATCH --account={account}")
        if constraint:
            optional_headers.append(f"#SBATCH --constraint={constraint}")
        if qos:
            optional_headers.append(f"#SBATCH --qos={qos}")

        launch_prefix = "srun "
        module_lines = "module load openmpi/4.1"
        if str(plan.execution_mode_intent).startswith("mpi_"):
            launch_prefix = f"srun --mpi=pmix -n {spec.ntasks} "
        elif str(plan.execution_mode_intent).startswith("gpu_"):
            # CUDA execution path is future-only; keep script explicit about unsupported mode.
            module_lines += "\n# module load cuda (future path; not yet wired in repo runtime)"

        run_command = str(
            p.get(
                "run_command",
                "python3 run_full_research_pipeline.py --mode experiment_batch --budget 20",
            )
        )
        return _SBATCH_TEMPLATE.format(
            job_name=spec.job_name,
            partition=spec.partition,
            nodes=spec.nodes,
            ntasks=spec.ntasks,
            cpus_per_task=spec.cpus_per_task,
            walltime=spec.walltime,
            mem=spec.mem,
            output_log=spec.output_log,
            error_log=spec.error_log,
            optional_headers=("\n".join(optional_headers) if optional_headers else ""),
            module_lines=module_lines,
            launch_prefix=launch_prefix,
            run_command=run_command,
        )

    def _materialize_artifacts(
        self,
        plan: ExecutionPlan,
        sbatch_script: str,
        artifact_dir: Path,
    ) -> Dict[str, str]:
        artifact_dir.mkdir(parents=True, exist_ok=True)
        stem = str(plan.plan_id)
        script_path = artifact_dir / f"{stem}.sbatch.sh"
        manifest_path = artifact_dir / f"{stem}.slurm_job_manifest.json"
        mapping_csv_path = artifact_dir / f"{stem}.workload_to_slurm_mapping.csv"
        readiness_md_path = artifact_dir / f"{stem}.backend_readiness.md"
        script_path.write_text(sbatch_script.rstrip() + "\n", encoding="utf-8")
        manifest_payload = {
            "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "backend": "slurm_bigred200",
            "requested_backend": plan.requested_backend,
            "task_type": plan.task_type,
            "execution_environment_intent": plan.execution_environment_intent,
            "execution_mode_intent": plan.execution_mode_intent,
            "execution_mode_actual": plan.execution_mode_actual,
            "execution_deferred_to_hpc": True,
            "plan": plan.to_dict(),
            "sbatch_script_path": str(script_path.resolve()),
            "submit_command": f"sbatch {script_path.name}",
            "notes": (
                "Generated locally for BigRed200 submission; no cluster job was submitted in this step."
            ),
        }
        manifest_path.write_text(json.dumps(manifest_payload, indent=2), encoding="utf-8")
        with mapping_csv_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "task_type",
                    "requested_backend",
                    "execution_mode_intent",
                    "nodes",
                    "ntasks",
                    "cpus_per_task",
                    "partition",
                    "walltime",
                    "mem",
                    "sbatch_script_path",
                    "slurm_job_manifest_path",
                ],
            )
            writer.writeheader()
            slurm = plan.slurm or SlurmResourceSpec()
            writer.writerow(
                {
                    "task_type": plan.task_type,
                    "requested_backend": plan.requested_backend,
                    "execution_mode_intent": plan.execution_mode_intent,
                    "nodes": slurm.nodes,
                    "ntasks": slurm.ntasks,
                    "cpus_per_task": slurm.cpus_per_task,
                    "partition": slurm.partition,
                    "walltime": slurm.walltime,
                    "mem": slurm.mem,
                    "sbatch_script_path": str(script_path.resolve()),
                    "slurm_job_manifest_path": str(manifest_path.resolve()),
                }
            )
        readiness_md_path.write_text(
            "\n".join(
                [
                    "# BigRed200 Backend Readiness",
                    "",
                    f"- task_type: `{plan.task_type}`",
                    f"- requested_backend: `{plan.requested_backend}`",
                    f"- execution_mode_intent: `{plan.execution_mode_intent}`",
                    f"- execution_mode_actual: `{plan.execution_mode_actual}`",
                    "- status: `submission_artifacts_generated`",
                    "- cluster_submission: `manual_on_bigred200`",
                    "",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        return {
            "sbatch_script_path": str(script_path.resolve()),
            "slurm_job_manifest_path": str(manifest_path.resolve()),
            "workload_to_slurm_mapping_csv": str(mapping_csv_path.resolve()),
            "backend_readiness_md": str(readiness_md_path.resolve()),
        }
