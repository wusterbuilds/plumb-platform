import uuid


class TestCreateDeal:
    async def test_create_minimal(self, client, auth_headers):
        resp = await client.post(
            "/deals",
            json={"deal_type": "construction_loan"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["deal_type"] == "construction_loan"
        assert data["status"] == "docs_received"
        assert data["version"] == 1
        assert data["revision_number"] == 1

    async def test_create_with_all_fields(self, client, auth_headers):
        resp = await client.post(
            "/deals",
            json={
                "deal_type": "construction_loan",
                "deal_subtype": "ground_up_residential",
                "capital_ask": "debt",
                "property_address": "456 Main St, Brooklyn, NY",
                "property_type": "multifamily_rental",
                "typed_extension": {"total_development_cost": 50_000_000},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["deal_subtype"] == "ground_up_residential"
        assert data["capital_ask"] == "debt"
        assert data["property_type"] == "multifamily_rental"
        assert data["typed_extension"]["total_development_cost"] == 50_000_000

    async def test_create_invalid_deal_type(self, client, auth_headers):
        resp = await client.post(
            "/deals",
            json={"deal_type": "invalid_type"},
            headers=auth_headers,
        )
        assert resp.status_code == 422


class TestListDeals:
    async def test_list_all(self, client, auth_headers, create_test_deal):
        await create_test_deal()
        await create_test_deal(deal_type="stabilized_debt")

        resp = await client.get("/deals", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2
        assert len(data["deals"]) == 2

    async def test_list_filter_by_status(self, client, auth_headers, create_test_deal):
        await create_test_deal()
        resp = await client.get("/deals", params={"status": "docs_received"}, headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] >= 1

    async def test_list_filter_by_deal_type(self, client, auth_headers, create_test_deal):
        await create_test_deal(deal_type="stabilized_debt")
        await create_test_deal(deal_type="construction_loan")

        resp = await client.get(
            "/deals", params={"deal_type": "stabilized_debt"}, headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["deals"][0]["deal_type"] == "stabilized_debt"

    async def test_list_ordered_by_updated_at_desc(self, client, auth_headers, create_test_deal):
        d1 = await create_test_deal()
        d2 = await create_test_deal()

        resp = await client.get("/deals", headers=auth_headers)
        deals = resp.json()["deals"]
        # Most recently created/updated should be first
        assert deals[0]["id"] == d2["id"]
        assert deals[1]["id"] == d1["id"]


class TestGetDeal:
    async def test_get_by_id(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.get(f"/deals/{deal['id']}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == deal["id"]

    async def test_get_nonexistent(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.get(f"/deals/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404


class TestUpdateDeal:
    async def test_update_with_correct_version(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.patch(
            f"/deals/{deal['id']}",
            json={"property_address": "Updated Address", "version": deal["version"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["property_address"] == "Updated Address"
        assert data["version"] == deal["version"] + 1

    async def test_update_wrong_version(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.patch(
            f"/deals/{deal['id']}",
            json={"property_address": "X", "version": 999},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_update_typed_extension(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        extension = {"total_development_cost": 75_000_000, "ltc_requested": 0.65}
        resp = await client.patch(
            f"/deals/{deal['id']}",
            json={"typed_extension": extension, "version": deal["version"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["typed_extension"] == extension

    async def test_update_only_sponsor(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal(property_address="Original Address")
        sponsor_data = {"name": "Sponsor Co", "track_record": "10 years"}
        resp = await client.patch(
            f"/deals/{deal['id']}",
            json={"sponsor": sponsor_data, "version": deal["version"]},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sponsor"] == sponsor_data
        assert data["property_address"] == "Original Address"


class TestDealEvents:
    async def test_create_deal_logs_event(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        resp = await client.get(f"/deals/{deal['id']}/events", headers=auth_headers)
        assert resp.status_code == 200
        events = resp.json()["events"]
        assert len(events) >= 1
        assert events[0]["event_type"] == "deal_created"

    async def test_update_deal_logs_event(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        await client.patch(
            f"/deals/{deal['id']}",
            json={"property_address": "New Addr", "version": deal["version"]},
            headers=auth_headers,
        )
        resp = await client.get(f"/deals/{deal['id']}/events", headers=auth_headers)
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "deal_updated" in event_types
