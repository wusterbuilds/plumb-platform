import uuid

from app.schemas.enums import DealStatus


async def _transition(client, deal_id, target, headers, **kwargs):
    """Helper to POST a state transition."""
    body = {"target_status": target, **kwargs}
    return await client.post(f"/deals/{deal_id}/transition", json=body, headers=headers)


async def _walk_forward(client, deal_id, statuses, headers):
    """Walk a deal through a list of forward statuses."""
    for s in statuses:
        resp = await _transition(client, deal_id, s, headers)
        assert resp.status_code == 200, f"Failed transition to {s}: {resp.json()}"
    return resp


class TestForwardFlow:
    async def test_full_pipeline(self, client, auth_headers, create_test_deal):
        """Walk through all 11 forward transitions from DOCS_RECEIVED to CLOSED."""
        deal = await create_test_deal()
        did = deal["id"]

        steps = [
            "classifying",
            "extracting",
            "extraction_review",
            "market_enrichment",  # human gate — actor_id comes from auth
            "model_building",
            "om_drafting",
            "om_review",
            "lender_outreach",      # human gate
            "tracking",
            "term_sheet_received",  # human gate
            "closed",              # human gate
        ]
        await _walk_forward(client, did, steps, auth_headers)

        resp = await client.get(f"/deals/{did}", headers=auth_headers)
        assert resp.json()["status"] == "closed"

    async def test_human_gate_extraction_review_to_market_enrichment(
        self, client, auth_headers, create_test_deal
    ):
        """EXTRACTION_REVIEW → MARKET_ENRICHMENT requires a human actor."""
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did, ["classifying", "extracting", "extraction_review"], auth_headers
        )
        # Auth headers include actor, so this should succeed
        resp = await _transition(client, did, "market_enrichment", auth_headers)
        assert resp.status_code == 200

    async def test_human_gate_om_review_to_lender_outreach(
        self, client, auth_headers, create_test_deal
    ):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client,
            did,
            [
                "classifying", "extracting", "extraction_review", "market_enrichment", "model_building", "om_drafting", "om_review",
            ],
            auth_headers,
        )
        resp = await _transition(client, did, "lender_outreach", auth_headers)
        assert resp.status_code == 200


class TestBackwardFlow:
    async def _get_to_model_building(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"],
            auth_headers,
        )
        return did

    async def test_model_building_to_extraction_review(
        self, client, auth_headers, create_test_deal
    ):
        did = await self._get_to_model_building(client, auth_headers, create_test_deal)
        resp = await _transition(
            client, did, "extraction_review", auth_headers, reason="Found errors"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "extraction_review"
        assert data["revision_number"] == 2  # incremented on backward

    async def test_om_review_to_extraction_review(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            [
                "classifying", "extracting", "extraction_review", "market_enrichment", "model_building", "om_drafting", "om_review",
            ],
            auth_headers,
        )
        resp = await _transition(
            client, did, "extraction_review", auth_headers, reason="OM numbers wrong"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "extraction_review"

    async def test_om_review_to_model_building(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            [
                "classifying", "extracting", "extraction_review", "market_enrichment", "model_building", "om_drafting", "om_review",
            ],
            auth_headers,
        )
        resp = await _transition(
            client, did, "model_building", auth_headers, reason="Recalculate model"
        )
        assert resp.status_code == 200

    async def test_tracking_to_om_drafting(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            [
                "classifying", "extracting", "extraction_review", "market_enrichment", "model_building", "om_drafting",
                "om_review", "lender_outreach", "tracking",
            ],
            auth_headers,
        )
        resp = await _transition(
            client, did, "om_drafting", auth_headers, reason="Lender wants revision"
        )
        assert resp.status_code == 200

    async def test_backward_without_reason_fails(self, client, auth_headers, create_test_deal):
        did = await self._get_to_model_building(client, auth_headers, create_test_deal)
        resp = await _transition(client, did, "extraction_review", auth_headers)
        assert resp.status_code == 422


class TestInvalidTransitions:
    async def test_skip_forward(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await _transition(client, deal["id"], "model_building", auth_headers)
        assert resp.status_code == 422

    async def test_closed_is_terminal(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            [
                "classifying", "extracting", "extraction_review", "market_enrichment", "model_building", "om_drafting",
                "om_review", "lender_outreach", "tracking",
                "term_sheet_received", "closed",
            ],
            auth_headers,
        )
        resp = await _transition(client, did, "tracking", auth_headers)
        assert resp.status_code == 422

    async def test_dead_is_terminal(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _transition(
            client, did, "dead", auth_headers, dead_reason="numbers_dont_work"
        )
        resp = await _transition(client, did, "docs_received", auth_headers)
        assert resp.status_code == 422

    async def test_extracting_cannot_skip_to_lender_outreach(
        self, client, auth_headers, create_test_deal
    ):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        resp = await _transition(client, did, "lender_outreach", auth_headers)
        assert resp.status_code == 422


class TestErrorStates:
    async def test_extracting_to_extraction_failed(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        resp = await _transition(client, did, "extraction_failed", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "extraction_failed"

    async def test_model_building_to_model_error(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"],
            auth_headers,
        )
        resp = await _transition(client, did, "model_error", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "model_error"

    async def test_retry_extraction(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        await _transition(client, did, "extraction_failed", auth_headers)
        resp = await _transition(client, did, "extracting", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "extracting"

    async def test_retry_model(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"],
            auth_headers,
        )
        await _transition(client, did, "model_error", auth_headers)
        resp = await _transition(client, did, "model_building", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "model_building"


class TestOnHold:
    async def test_active_to_on_hold(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        resp = await _transition(client, did, "on_hold", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "on_hold"

    async def test_resume_from_on_hold(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        await _transition(client, did, "on_hold", auth_headers)
        resp = await _transition(client, did, "extracting", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "extracting"

    async def test_resume_to_wrong_state_fails(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        await _transition(client, did, "on_hold", auth_headers)
        # Try to resume to a different state than where we were
        resp = await _transition(client, did, "model_building", auth_headers)
        assert resp.status_code == 422

    async def test_on_hold_clears_previous_status_on_resume(
        self, client, auth_headers, create_test_deal
    ):
        """Fix 3 verification: previous_status is cleared on resume."""
        deal = await create_test_deal()
        did = deal["id"]
        # Go to extracting, hold, resume
        await _walk_forward(client, did, ["classifying", "extracting"], auth_headers)
        await _transition(client, did, "on_hold", auth_headers)
        await _transition(client, did, "extracting", auth_headers)
        # Now advance further and hold again
        await _walk_forward(
            client, did, ["extraction_review", "market_enrichment", "model_building"], auth_headers
        )
        await _transition(client, did, "on_hold", auth_headers)
        # Should resume to model_building (the latest state before hold)
        resp = await _transition(client, did, "model_building", auth_headers)
        assert resp.status_code == 200
        assert resp.json()["status"] == "model_building"


class TestKillDeal:
    async def test_kill_with_reason(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await _transition(
            client, deal["id"], "dead", auth_headers, dead_reason="numbers_dont_work"
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "dead"

    async def test_kill_without_reason_fails(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await _transition(client, deal["id"], "dead", auth_headers)
        assert resp.status_code == 422


class TestTransitionEvents:
    async def test_forward_transition_logged(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]
        await _transition(client, did, "classifying", auth_headers)

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "state_transition" in event_types

    async def test_backward_transition_event_includes_reason(
        self, client, auth_headers, create_test_deal
    ):
        deal = await create_test_deal()
        did = deal["id"]
        await _walk_forward(
            client, did,
            ["classifying", "extracting", "extraction_review", "market_enrichment", "model_building"],
            auth_headers,
        )
        await _transition(
            client, did, "extraction_review", auth_headers, reason="Fix extraction"
        )

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        backward_events = [e for e in events if e["event_type"] == "backward_transition"]
        assert len(backward_events) == 1
        assert backward_events[0]["payload"]["reason"] == "Fix extraction"
