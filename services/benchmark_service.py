"""Task sets, benchmark runs, and local scorecards.

User-owned task sets are run against selected models with deterministic scoring;
each model gets a local Scorecard (pass rate, average latency/cost). Persistence
is local SQLite. The model call is injected (``generate_fn``) so tests run with a
deterministic fake and never touch the network or a real provider.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable, Optional

from sqlalchemy.orm import Session

from core.benchmark import grade
from db.models import Base, BenchmarkRun, BenchmarkTask, ModelRegistry, Scorecard, TaskSet

# (response_text, latency_ms, cost_usd) for a model on a prompt.
GenerateFn = Callable[[ModelRegistry, str], tuple[str, float, float]]

_BENCH_TABLES = [
    TaskSet.__table__, BenchmarkTask.__table__, BenchmarkRun.__table__, Scorecard.__table__,
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_tables(session: Session) -> None:
    """Provision the benchmark tables on the bound DB if missing (create_all adds
    only missing tables; it never alters existing ones). No migration framework."""
    bind = session.get_bind()
    if bind is not None:
        Base.metadata.create_all(bind, tables=_BENCH_TABLES)


def create_task_set(session: Session, name: str, description: Optional[str] = None) -> TaskSet:
    ensure_tables(session)
    ts = TaskSet(id=str(uuid.uuid4()), name=name, description=description, created_at=_now())
    session.add(ts)
    session.commit()
    return ts


def add_task(
    session: Session,
    task_set_id: str,
    prompt: str,
    expected: Optional[str] = None,
    grader: str = "contains",
    task_type: str = "simple",
) -> BenchmarkTask:
    task = BenchmarkTask(
        id=str(uuid.uuid4()), task_set_id=task_set_id, prompt=prompt,
        expected=expected, grader=grader, task_type=task_type, created_at=_now(),
    )
    session.add(task)
    session.commit()
    return task


def get_task_set_by_name(session: Session, name: str) -> Optional[TaskSet]:
    return (
        session.query(TaskSet)
        .filter_by(name=name)
        .order_by(TaskSet.created_at.desc())
        .first()
    )


def run_benchmark(
    session: Session,
    task_set: TaskSet,
    models: list[ModelRegistry],
    generate_fn: GenerateFn,
) -> BenchmarkRun:
    """Run every task in *task_set* against each model and persist one Scorecard
    per model. ``generate_fn`` performs the model call (injected for testability).

    A failure mid-run rolls back the whole run. SQLAlchemy autoflushes the pending
    ``BenchmarkRun`` row when ``task_set.tasks`` lazy-loads, and on SQLite that row
    can otherwise survive ``session.close()`` as an orphan with zero scorecards.
    Rolling back guarantees a run is persisted only when it actually completed."""
    ensure_tables(session)
    run = BenchmarkRun(id=str(uuid.uuid4()), task_set_id=task_set.id, status="completed", created_at=_now())
    session.add(run)

    try:
        tasks = list(task_set.tasks)
        for model in models:
            passed = 0
            latency_total = 0.0
            cost_total = 0.0
            for task in tasks:
                response, latency_ms, cost_usd = generate_fn(model, task.prompt)
                if grade(task.grader, response, task.expected):
                    passed += 1
                latency_total += latency_ms or 0.0
                cost_total += cost_usd or 0.0
            n = len(tasks)
            session.add(Scorecard(
                id=str(uuid.uuid4()), run_id=run.id, task_set_id=task_set.id,
                provider=model.provider, model_id=model.external_model_id,
                tasks_total=n, tasks_passed=passed,
                score=(passed / n if n else 0.0),
                avg_latency_ms=(latency_total / n if n else 0.0),
                avg_cost_usd=(cost_total / n if n else 0.0),
                created_at=_now(),
            ))
        session.commit()
    except Exception:
        session.rollback()
        raise
    return run


def list_scorecards(session: Session, task_set_id: Optional[str] = None) -> list[Scorecard]:
    query = session.query(Scorecard)
    if task_set_id:
        query = query.filter_by(task_set_id=task_set_id)
    return query.order_by(Scorecard.score.desc()).all()


def scores_by_model(session: Session, task_set_id: Optional[str] = None) -> dict[str, float]:
    """Best (max) scorecard score per model id, optionally scoped to one task set.
    Returns ``{}`` when no scorecards exist. Feeds scorecard-aware routing; models
    absent from the map simply have no benchmark signal.

    The key is ``Scorecard.model_id``, which ``run_benchmark`` writes from
    ``ModelRegistry.external_model_id``. Routing joins on ``external_model_id``, so
    the keys line up today. That identity is implicit (no FK); when ModelSource
    identity lands and external ids stop being globally unique across sources, the
    join must move to a source-qualified id."""
    ensure_tables(session)
    query = session.query(Scorecard)
    if task_set_id:
        query = query.filter_by(task_set_id=task_set_id)
    best: dict[str, float] = {}
    for card in query.all():
        score = card.score if card.score is not None else 0.0
        if card.model_id not in best or score > best[card.model_id]:
            best[card.model_id] = score
    return best
