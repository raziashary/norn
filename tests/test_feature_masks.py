from dataclasses import replace

import pytest
from conftest import clock, request

from norn.contracts.errors import NornError
from norn.contracts.evidence import Epistemic, EpistemicState
from norn.features import actions, views
from norn.features.salience import NeutralSalience
from norn.retrieval.contracts import RecallRequest
from norn.retrieval.exact import eligible


def test_neutral_salience_cannot_become_an_observed_zero():
    with pytest.raises(NornError, match="SALIENCE_TREATMENT_NOT_SUPPORTED"):
        NeutralSalience(present=True)
    with pytest.raises(NornError, match="SALIENCE_TREATMENT_NOT_SUPPORTED"):
        NeutralSalience(value=0)


def action_request(origin=Epistemic.DIRECT_OBSERVATION):
    original = request()
    text = "Alex step 0 tool restart result exit0 at 2026-10-20T09:00:00+00:00"
    fixture = replace(
        original.atoms[0],
        predicate="observed_action",
        value=replace(original.atoms[0].value, value="exit0"),
        end=len(text),
        epistemic=EpistemicState(origin),
        qualifiers=(
            ("action_step", "0"),
            ("attempted_tool", "restart"),
            ("observed_result", "exit0"),
            ("observed_at", "2026-10-20T09:00:00+00:00"),
        ),
    )
    return replace(original, content=text.encode(), atoms=(fixture,))


def test_actual_observed_action_source_sequence_and_neutral_mask(engine):
    written = action_request()
    engine.write(written)
    records = eligible(engine, RecallRequest("restart", clock())).records
    view = actions.derive(records)
    assert view.applicability == "OBSERVED" and view.steps[0].result == "exit0"
    assert view.steps[0].record_key == records[0].key
    assert engine.sources.resolve(view.context.sources[0]) == written.content
    assert "reward" not in view.text and "success" not in view.text
    value = views.derive(records)
    assert value.mask == (True, True, True)
    assert NeutralSalience().present is False and NeutralSalience().value is None


def test_absence_hypothesis_and_full_fanout_keep_explicit_masks(engine):
    engine.write(action_request(Epistemic.HYPOTHESIS))
    records = eligible(engine, RecallRequest("restart", clock())).records
    assert actions.derive(records).applicability == "NOT_APPLICABLE"
    selective, full = views.derive(records), views.derive(records, full_fanout=True)
    assert selective.texts == full.texts and selective.mask == (True, True, False)
    assert selective.invocations == (True, True, False)
    assert full.invocations == (True, True, True)
    with pytest.raises(NornError, match="ACTION_INPUT_MISSING"):
        actions.derive((replace(records[0], origin="DIRECT_OBSERVATION", qualifiers_json="[]"),))
