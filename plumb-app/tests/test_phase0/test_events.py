import uuid


class TestEventCreation:
    async def test_deal_creation_event(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.get(f"/deals/{deal['id']}/events", headers=auth_headers)
        events = resp.json()["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "deal_created"
        assert events[0]["payload"]["deal_type"] == "construction_loan"

    async def test_state_transition_event(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await client.post(
            f"/deals/{did}/transition",
            json={"target_status": "classifying"},
            headers=auth_headers,
        )
        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        transition_events = [e for e in events if e["event_type"] == "state_transition"]
        assert len(transition_events) == 1
        assert transition_events[0]["payload"]["from_status"] == "docs_received"
        assert transition_events[0]["payload"]["to_status"] == "classifying"

    async def test_events_include_actor_id(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.get(f"/deals/{deal['id']}/events", headers=auth_headers)
        events = resp.json()["events"]
        # All events from API calls should have actor_id
        for event in events:
            assert event["actor_id"] is not None

    async def test_events_include_correct_payload(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal(property_address="789 Broadway, NY")
        resp = await client.get(f"/deals/{deal['id']}/events", headers=auth_headers)
        events = resp.json()["events"]
        create_event = [e for e in events if e["event_type"] == "deal_created"][0]
        assert create_event["payload"]["property_address"] == "789 Broadway, NY"

    async def test_events_ordered_by_timestamp_asc(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        # Create multiple events via transitions
        await client.post(
            f"/deals/{did}/transition",
            json={"target_status": "classifying"},
            headers=auth_headers,
        )
        await client.post(
            f"/deals/{did}/transition",
            json={"target_status": "extracting"},
            headers=auth_headers,
        )

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        timestamps = [e["timestamp"] for e in events]
        assert timestamps == sorted(timestamps)

    async def test_backward_transition_event_has_reason(
        self, client, auth_headers, create_test_deal
    ):
        deal = await create_test_deal()
        did = deal["id"]
        # Walk to model_building
        for s in ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"]:
            await client.post(
                f"/deals/{did}/transition",
                json={"target_status": s},
                headers=auth_headers,
            )
        # Go backward
        await client.post(
            f"/deals/{did}/transition",
            json={"target_status": "extraction_review", "reason": "Numbers off"},
            headers=auth_headers,
        )

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        backward = [e for e in events if e["event_type"] == "backward_transition"]
        assert len(backward) == 1
        assert backward[0]["payload"]["reason"] == "Numbers off"

    async def test_events_for_nonexistent_deal(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/deals/{fake_id}/events", headers=auth_headers)
        assert resp.status_code == 404

    async def test_revision_number_on_backward(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        for s in ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"]:
            await client.post(
                f"/deals/{did}/transition",
                json={"target_status": s},
                headers=auth_headers,
            )
        await client.post(
            f"/deals/{did}/transition",
            json={"target_status": "extraction_review", "reason": "Fix"},
            headers=auth_headers,
        )

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        backward = [e for e in events if e["event_type"] == "backward_transition"][0]
        assert backward["revision_number"] == 2
