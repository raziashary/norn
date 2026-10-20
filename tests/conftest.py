"""All stores and destructive controls are isolated in pytest temporary directories.

No test loads .env, calls a provider, opens a listener, or targets an existing DB.
"""

from datetime import UTC, datetime

import pytest

from norn.canonical.registry import WriteRequest
from norn.contracts.evidence import Epistemic, EpistemicState, TaggedValue
from norn.contracts.identity import Namespace
from norn.contracts.time import QueryClock, TimeKind, TimeValue
from norn.extraction.atoms import FixtureAtom
from norn.governance.access import HostIdentity
from norn.integration.engine import Engine

HOST = HostIdentity(Namespace("tenant", "workspace", "local"), "operator")
TUESDAY = datetime(2026, 10, 20, 9, tzinfo=UTC)


def request(occurrence="tuesday", delivery=None, place="ZoneA", *, scope="parking", origin=None):
    text = f"Alex parked in {place}."
    fixture = FixtureAtom(
        "Alex",
        "parked_in",
        TaggedValue("TEXT", place),
        0,
        len(text.encode()),
        origin or EpistemicState(Epistemic.USER_REPORTED),
        (("scope", scope),),
    )
    return WriteRequest(
        "req-" + occurrence,
        "operator",
        delivery or occurrence,
        occurrence,
        text.encode(),
        TimeValue(TimeKind.EXACT, TUESDAY),
        TUESDAY,
        (fixture,),
    )


def clock(snapshot=None, *, valid=TUESDAY, knowledge=None):
    now = datetime(2030, 1, 1, tzinfo=UTC)
    return QueryClock(now, "UTC", "VALID_TIME", valid, knowledge or now, snapshot)


@pytest.fixture
def engine(tmp_path):
    with Engine(tmp_path / "store", HOST, create=True) as instance:
        instance.access.bootstrap()
        yield instance
