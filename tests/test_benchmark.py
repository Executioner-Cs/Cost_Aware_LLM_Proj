"""
Benchmark task sets, runs, and scorecards. Deterministic grading; the model call
is a fake, so no network and no real provider are involved.
"""
from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.benchmark import grade
from db.models import Base, ModelRegistry, Scorecard
from services import benchmark_service as bench


@pytest.fixture
def session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'b.db'}")
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    yield s
    s.close()


def _model(ext, provider="openai", cost=1.0):
    return ModelRegistry(
        id=ext, account_id="a", provider=provider, external_model_id=ext,
        display_name=ext, tier="small", context_window=128_000,
        cost_per_1m_input=cost, cost_per_1m_output=cost, supports_json=1,
        supports_tools=1, supports_vision=0, enabled=1, discovered_at="2026-01-01",
    )


# --------------------------------------------------------------------------- #
# Grading
# --------------------------------------------------------------------------- #

def test_grade_exact():
    assert grade("exact", "4", "4") is True
    assert grade("exact", "  4 ", "4") is True
    assert grade("exact", "four", "4") is False


def test_grade_contains():
    assert grade("contains", "the answer is Paris.", "paris") is True
    assert grade("contains", "London", "paris") is False


def test_grade_json_valid():
    assert grade("json_valid", '{"a": 1}', None) is True
    assert grade("json_valid", "not json", None) is False


def test_grade_unknown_raises():
    with pytest.raises(ValueError):
        grade("vibes", "x", "y")


# --------------------------------------------------------------------------- #
# Task sets + runs + scorecards
# --------------------------------------------------------------------------- #

def test_create_task_set_and_add_tasks(session):
    ts = bench.create_task_set(session, "math", "basic arithmetic")
    bench.add_task(session, ts.id, "2+2?", expected="4", grader="exact")
    bench.add_task(session, ts.id, "capital of France?", expected="paris", grader="contains")
    fetched = bench.get_task_set_by_name(session, "math")
    assert fetched.id == ts.id
    assert len(fetched.tasks) == 2


def test_run_benchmark_scores_per_model(session):
    ts = bench.create_task_set(session, "qa")
    bench.add_task(session, ts.id, "2+2?", expected="4", grader="exact")
    bench.add_task(session, ts.id, "capital of France?", expected="paris", grader="contains")

    good = _model("good-model")
    bad = _model("bad-model")

    # Deterministic fake: 'good' answers correctly, 'bad' never does. No network.
    answers = {
        ("good-model", "2+2?"): "4",
        ("good-model", "capital of France?"): "It is Paris.",
    }

    def fake_generate(model, prompt):
        return answers.get((model.external_model_id, prompt), "wrong"), 100.0, 0.0001

    run = bench.run_benchmark(session, ts, [good, bad], fake_generate)
    cards = {c.model_id: c for c in session.query(Scorecard).filter_by(run_id=run.id).all()}

    assert cards["good-model"].tasks_passed == 2 and cards["good-model"].score == 1.0
    assert cards["bad-model"].tasks_passed == 0 and cards["bad-model"].score == 0.0
    assert cards["good-model"].avg_latency_ms == 100.0


def test_list_scorecards_sorted_by_score(session):
    ts = bench.create_task_set(session, "s")
    bench.add_task(session, ts.id, "q", expected="a", grader="contains")
    hi = _model("hi")
    lo = _model("lo")

    def fake_generate(model, prompt):
        return ("a" if model.external_model_id == "hi" else "z"), 10.0, 0.0

    bench.run_benchmark(session, ts, [lo, hi], fake_generate)
    cards = bench.list_scorecards(session, ts.id)
    assert [c.model_id for c in cards] == ["hi", "lo"]  # best score first


def test_ensure_tables_on_db_without_them(tmp_path):
    # A DB created before the benchmark tables existed must gain them lazily.
    from sqlalchemy import inspect as sa_inspect
    engine = create_engine(f"sqlite:///{tmp_path / 'old.db'}")
    older = [t for name, t in Base.metadata.tables.items() if not name.startswith(("task_sets", "benchmark_", "scorecards"))]
    Base.metadata.create_all(engine, tables=older)
    assert "task_sets" not in sa_inspect(engine).get_table_names()

    s = sessionmaker(bind=engine)()
    bench.ensure_tables(s)
    names = set(sa_inspect(engine).get_table_names())
    assert {"task_sets", "benchmark_tasks", "benchmark_runs", "scorecards"} <= names
    s.close()
