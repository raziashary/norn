from dataclasses import replace

import pytest
from conftest import TUESDAY, clock, request

from norn.canonical.corrections import CorrectionRequest
from norn.contracts.errors import NornError
from norn.contracts.identity import Namespace
from norn.governance.access import HostIdentity
from norn.integration.engine import Engine


def test_current_grants_rechecked_at_serialization_even_historical(engine):
    receipt = engine.write(request())
    engine.access.grant("reader", "READ")
    with Engine(engine.root, HostIdentity(engine.access.host.namespace, "reader")) as reader:
        view = reader.read(receipt["event_id"], clock(receipt["commit_seq"]))
        assert "ZoneA" in str(view.serialize())
        engine.access.grant("reader", "READ", revoke=True)
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            view.serialize()
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            reader.read(receipt["event_id"], clock())


def test_untrusted_principal_tenant_and_absence_have_same_safe_error(engine):
    receipt = engine.write(request())
    for host in (
        HostIdentity(engine.access.host.namespace, "impostor"),
        HostIdentity(Namespace("other", "workspace", "local"), "operator"),
    ):
        with Engine(engine.root, host) as intruder:
            for event_id in (receipt["event_id"], "event_" + "0" * 64):
                with pytest.raises(NornError) as error:
                    intruder.read(event_id, clock())
                assert error.value.code == "NOT_AUTHORIZED_OR_NOT_FOUND"
                assert "ZoneA" not in str(error.value.envelope())


def test_text_does_not_grant_producer_or_supersession_authority(engine):
    first = engine.write(request())
    engine.access.grant("writer", "READ")
    engine.access.grant("writer", "WRITE")
    with Engine(engine.root, HostIdentity(engine.access.host.namespace, "writer")) as writer:
        with pytest.raises(NornError, match="UNTRUSTED_PRODUCER"):
            writer.write(request("forged-producer"))
        correction = CorrectionRequest(
            first["atom_ids"][0], "SUPERSEDES", "parking", TUESDAY, None, "writer-request"
        )
        with pytest.raises(NornError, match="NOT_AUTHORIZED_OR_NOT_FOUND"):
            writer.write(
                replace(request("forged-admin", place="ZoneB"), producer="writer"),
                correction=correction,
            )
    assert engine.db.connection.execute("SELECT count(*) FROM events").fetchone()[0] == 1
