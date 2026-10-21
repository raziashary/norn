import sqlite3
from threading import Event

import pytest
from conftest import clock, request

from norn.contracts.budgets import QueryBudget
from norn.contracts.errors import NornError
from norn.retrieval import assembly, dense, exact, lexical
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.service import UnicodeTokenizer


def test_global_attempt_and_deadline_accounting():
    ticks = [0.0]
    budget = QueryBudget(100, now=lambda: ticks[0], max_model_calls=2, max_model_tokens=1024)
    budget.attempt(512)
    budget.complete(512, 20)
    budget.attempt(512)
    assert budget.usage()["model_calls"] == 2 and budget.model_tokens == 532
    with pytest.raises(NornError, match="MODEL_CALL_BUDGET"):
        budget.attempt(512)
    ticks[0] = 0.101
    with pytest.raises(NornError, match="QUERY_DEADLINE"):
        budget.checkpoint()


def test_cancelled_query_has_safe_unavailable_envelope(engine):
    engine.write(request())
    engine.project()
    stop = Event()
    stop.set()
    result = engine.recall(
        RecallRequest("CANARY_API_KEY_PRIVATE", clock()), cancelled=stop
    ).serialize()
    assert result["status"] == "VERIFICATION_UNAVAILABLE" and result["reason"] == "QUERY_CANCELLED"
    assert not result["evidence"] and "CANARY_API_KEY_PRIVATE" not in str(result)
    good = engine.recall(RecallRequest("Alex", clock(), predicates=("parked_in",))).serialize()
    assert good["status"] == "SUPPORTED"


def test_sql_deadline_interrupts_actual_work_and_restores_connection():
    connection = sqlite3.connect(":memory:")
    connection.execute("CREATE TABLE t(x)")
    connection.executemany("INSERT INTO t VALUES(?)", ((i,) for i in range(100)))
    with QueryBudget(1000).sqlite_guard(connection):
        assert connection.execute("SELECT count(*) FROM t").fetchone()[0] == 100
    with pytest.raises(NornError, match="QUERY_DEADLINE"):
        with QueryBudget(1).sqlite_guard(connection):
            connection.execute("SELECT count(*) FROM t a,t b,t c,t d").fetchone()
    assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
    assert connection.execute("SELECT 42").fetchone()[0] == 42
    connection.close()


def test_ranking_and_packing_share_cancellation_owner(engine):
    engine.write(request())
    query = RecallRequest("Alex", clock(), requested_fields=("parked_in",))
    corpus = exact.eligible(engine, query)
    stop = Event()
    budget = QueryBudget(1000, stop)
    unit = (1.0, *([0.0] * 383))
    assert dense.search(corpus, unit, {r.key: unit for r in corpus.records}, 1, budget.checkpoint)
    stop.set()
    for run in (
        lambda: lexical.search(corpus, "Alex", 1, checkpoint=budget.checkpoint),
        lambda: dense.search(
            corpus, unit, {r.key: unit for r in corpus.records}, 1, budget.checkpoint
        ),
        lambda: assembly.assemble(
            corpus.records, query, UnicodeTokenizer(), complete=True, checkpoint=budget.checkpoint
        ),
    ):
        with pytest.raises(NornError, match="QUERY_CANCELLED"):
            run()
