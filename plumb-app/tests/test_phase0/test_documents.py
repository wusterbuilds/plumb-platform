import io
import uuid
from unittest.mock import patch


class TestUploadDocument:
    async def test_upload_pdf(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        file_content = b"%PDF-1.4 fake pdf content"
        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/test.pdf", len(file_content))
            resp = await client.post(
                f"/deals/{did}/documents",
                files={"file": ("test.pdf", io.BytesIO(file_content), "application/pdf")},
                headers=auth_headers,
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["filename"] == "test.pdf"
        assert data["mime_type"] == "application/pdf"
        assert data["s3_key"] == f"deals/{did}/documents/test.pdf"
        assert data["file_size"] == len(file_content)
        assert data["deal_id"] == did

    async def test_upload_logs_event(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/doc.pdf", 100)
            await client.post(
                f"/deals/{did}/documents",
                files={"file": ("doc.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )

        resp = await client.get(f"/deals/{did}/events", headers=auth_headers)
        events = resp.json()["events"]
        event_types = [e["event_type"] for e in events]
        assert "doc_uploaded" in event_types

    async def test_upload_to_nonexistent_deal(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = ("key", 100)
            resp = await client.post(
                f"/deals/{fake_id}/documents",
                files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )
        assert resp.status_code == 404


class TestListDocuments:
    async def test_list_documents(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/a.pdf", 50)
            await client.post(
                f"/deals/{did}/documents",
                files={"file": ("a.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )
            mock_upload.return_value = (f"deals/{did}/documents/b.pdf", 60)
            await client.post(
                f"/deals/{did}/documents",
                files={"file": ("b.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )

        resp = await client.get(f"/deals/{did}/documents", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 2


class TestGetDocument:
    async def test_get_document(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/test.pdf", 100)
            upload_resp = await client.post(
                f"/deals/{did}/documents",
                files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )
        doc_id = upload_resp.json()["id"]

        resp = await client.get(f"/deals/{did}/documents/{doc_id}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == doc_id

    async def test_get_document_wrong_deal(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/test.pdf", 100)
            upload_resp = await client.post(
                f"/deals/{did}/documents",
                files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )
        doc_id = upload_resp.json()["id"]

        other_deal = await create_test_deal()
        resp = await client.get(
            f"/deals/{other_deal['id']}/documents/{doc_id}", headers=auth_headers
        )
        assert resp.status_code == 404


class TestDownloadDocument:
    async def test_download_url(self, client, auth_headers, create_test_deal):
        deal = await create_test_deal()
        did = deal["id"]

        with patch("app.api.documents.upload_document") as mock_upload:
            mock_upload.return_value = (f"deals/{did}/documents/test.pdf", 100)
            upload_resp = await client.post(
                f"/deals/{did}/documents",
                files={"file": ("test.pdf", io.BytesIO(b"data"), "application/pdf")},
                headers=auth_headers,
            )
        doc_id = upload_resp.json()["id"]

        with patch("app.api.documents.get_presigned_url") as mock_url:
            mock_url.return_value = "http://minio:9000/plumb-documents/deals/test.pdf?signed"
            resp = await client.get(
                f"/deals/{did}/documents/{doc_id}/download", headers=auth_headers
            )
        assert resp.status_code == 200
        assert "download_url" in resp.json()
