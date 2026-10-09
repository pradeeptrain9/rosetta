"""Turn repair traces into a fine-tuning set, then train the fast tier on them.

The economics of the pipeline are set by the repair loop: it runs on the
reasoning tier because diagnosing a scale bug needs reasoning. But the repairs
are highly repetitive across programs - the same dozen COBOL semantics get
mistranslated again and again. Every accepted repair is therefore a labelled
example, and a much smaller model can be taught to do most of them.

This is CROSS-MODEL distillation, not same-family: Token Factory fine-tunes no
Nemotron model, so Nemotron Ultra generates the labels and a fine-tunable
student (Llama, Qwen, Gemma or gpt-oss) learns them.

`export` writes the JSONL. `upload` and `train` drive Token Factory's
fine-tuning API. `train` is intentionally thin: it submits the job and prints
the id, because a fine-tune outlives a CLI invocation.
"""

from __future__ import annotations

import json
from pathlib import Path

from openai import OpenAI

from .config import Settings
from .models import MigrationResult
from .repair import _PROMPT as REPAIR_PROMPT, _SYSTEM as REPAIR_SYSTEM


def export_traces(results: list[MigrationResult], path: str | Path) -> int:
    """Write accepted repairs as chat-format JSONL.

    Only repairs that strictly reduced the failure count are kept. A repair that
    regressed is a negative example and teaching the fast tier to imitate it
    would make the distilled model worse.
    """
    out = Path(path)
    written = 0
    with out.open("w") as fh:
        for r in results:
            for attempt in r.repairs:
                if attempt.failures_after < 0:
                    continue
                if attempt.failures_after >= attempt.failures_before:
                    continue
                if not attempt.patched_code.strip():
                    continue
                record = {
                    "messages": [
                        {"role": "system", "content": REPAIR_SYSTEM},
                        {
                            "role": "user",
                            "content": _reconstruct_user_turn(r, attempt),
                        },
                        {
                            "role": "assistant",
                            "content": f"```python\n{attempt.patched_code}```",
                        },
                    ],
                    "metadata": {
                        "program_id": r.program_id,
                        "iteration": attempt.iteration,
                        "failures_before": attempt.failures_before,
                        "failures_after": attempt.failures_after,
                        "failure_kinds": attempt.failure_kinds,
                    },
                }
                fh.write(json.dumps(record) + "\n")
                written += 1
    return written


def _reconstruct_user_turn(result: MigrationResult, attempt) -> str:
    from .translate import SEMANTIC_RULES

    return REPAIR_PROMPT.format(
        cobol=Path(result.path).read_text(errors="replace") if Path(result.path).exists() else "",
        python="<the port at this iteration>",
        n_failing=attempt.failures_before,
        n_total=result.vectors_total,
        failures=attempt.diff_excerpt,
        rules=SEMANTIC_RULES,
    )


def upload_dataset(settings: Settings, path: str | Path) -> str:
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    with Path(path).open("rb") as fh:
        uploaded = client.files.create(file=fh, purpose="fine-tune")
    return uploaded.id


def start_finetune(
    settings: Settings,
    file_id: str,
    base_model: str,
    suffix: str = "rosetta-repair",
    epochs: int = 3,
    lora_r: int = 16,
    lora_alpha: int = 32,
) -> str:
    """Submit a LoRA fine-tune of the student on the repair traces.

    base_model must be one Token Factory can fine-tune. Passing a Nemotron here
    is rejected by the API - see config.FINE_TUNABLE_STUDENTS.
    """
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    job = client.fine_tuning.jobs.create(
        training_file=file_id,
        model=base_model,
        suffix=suffix,
        hyperparameters={
            "n_epochs": epochs,
            # Adapter-only training: the repair behaviour is a narrow skill laid
            # over a general model, and a full fine-tune would cost far more for
            # no benefit on a few hundred examples.
            "lora": True,
            "lora_r": lora_r,
            "lora_alpha": lora_alpha,
        },
        seed=42,
    )
    return job.id


def finetune_status(settings: Settings, job_id: str) -> dict:
    """Report a fine-tune job.

    A succeeded job yields downloadable CHECKPOINTS; it does not necessarily
    become a servable model id. `fine_tuned_model` is therefore often null even
    on success, and `servable` says plainly whether the adapter can be called
    yet or still needs deploying.
    """
    client = OpenAI(api_key=settings.api_key, base_url=settings.base_url)
    job = client.fine_tuning.jobs.retrieve(job_id)
    tuned = getattr(job, "fine_tuned_model", None)
    status = getattr(job, "status", "unknown")
    return {
        "id": job.id,
        "status": status,
        "base_model": getattr(job, "model", None),
        "fine_tuned_model": tuned,
        "trained_tokens": getattr(job, "trained_tokens", None),
        "servable": bool(tuned),
        "next_step": (
            f"call it as model={tuned!r}"
            if tuned
            else "download the checkpoints and deploy the adapter before it can be called"
            if status == "succeeded"
            else f"wait: job is {status}"
        ),
    }
