"""Extraction tools — real implementations calling parsing, LLM, and confidence scoring."""

import asyncio
import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.tools.base import PlumbTool, ToolContext, ToolPermission, ToolResult

logger = logging.getLogger(__name__)


class ClassifyDocumentTool(PlumbTool):
    name = "classify_document"
    description = "Classify a document by type (pro_forma, appraisal, etc.) given filename and first pages."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document to classify"},
            },
            "required": ["document_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, document_id: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db or not _ctx.llm_client:
            return ToolResult(success=False, error="ToolContext with db and llm_client required")

        from app.models.document import Document
        from app.storage.s3 import download_document

        db: AsyncSession = _ctx.db
        doc_uuid = uuid.UUID(document_id)

        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            return ToolResult(success=False, error=f"Document {document_id} not found")

        # Download and parse first pages
        file_bytes = await asyncio.to_thread(download_document, doc.s3_key)

        is_excel = (
            doc.filename.endswith((".xlsx", ".xls", ".csv"))
            or (doc.mime_type and ("excel" in doc.mime_type or "spreadsheet" in doc.mime_type))
        )
        is_pdf = doc.filename.endswith(".pdf") or (doc.mime_type and "pdf" in doc.mime_type)

        page_images = []
        sheet_preview = None
        if is_pdf:
            from app.parsing.pdf import pdf_to_page_images
            pages = await asyncio.to_thread(pdf_to_page_images, file_bytes, 150)
            for page in pages[:3]:
                page_images.append(page.to_claude_content())
        elif is_excel:
            from app.parsing.excel import extract_excel_content, format_sheets_for_llm
            excel_content = await asyncio.to_thread(extract_excel_content, file_bytes)
            sheet_preview = format_sheets_for_llm(excel_content)

        # Call LLM for classification
        deal_context = {"filename": doc.filename}
        task_data = {
            "filename": doc.filename,
            "mime_type": doc.mime_type or "application/octet-stream",
            "page_images": page_images if page_images else None,
            "sheet_preview": sheet_preview,
        }
        llm_result = await _ctx.llm_client.execute(
            "classify_document", deal_context, task_data,
            db=db, deal_id=_ctx.deal_id,
        )

        doc_type = llm_result.get("document_type", "unknown")
        confidence = llm_result.get("confidence", 0.5)

        # Update document record
        doc.document_type = doc_type
        doc.classification_confidence = confidence
        doc.status = "classified"
        await db.flush()

        return ToolResult(data={
            "document_id": document_id,
            "document_type": doc_type,
            "confidence": confidence,
            "filename": doc.filename,
        })


class ExtractFromPDFTool(PlumbTool):
    name = "extract_from_pdf"
    description = "Extract structured fields from a PDF document using the appropriate extraction prompt."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the document"},
                "document_type": {"type": "string", "description": "Type of document (pro_forma, appraisal, etc.)"},
            },
            "required": ["document_id", "document_type"],
        }

    async def execute(self, _ctx: ToolContext | None = None, document_id: str = "", document_type: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db or not _ctx.llm_client:
            return ToolResult(success=False, error="ToolContext with db and llm_client required")

        from app.extraction.confidence import assign_flag, score_confidence
        from app.extraction.handlers import get_prompt_name
        from app.models.document import Document
        from app.models.extraction import ExtractedValue
        from app.parsing.pdf import chunk_pages, pdf_to_page_images
        from app.storage.s3 import download_document

        db: AsyncSession = _ctx.db
        doc_uuid = uuid.UUID(document_id)

        prompt_name = get_prompt_name(document_type)
        if not prompt_name:
            return ToolResult(success=False, error=f"No extraction prompt for document type: {document_type}")

        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            return ToolResult(success=False, error=f"Document {document_id} not found")

        # Download and render PDF pages
        file_bytes = await asyncio.to_thread(download_document, doc.s3_key)
        pages = await asyncio.to_thread(pdf_to_page_images, file_bytes, 150)
        chunks = chunk_pages(pages, max_pages=25, overlap=1)

        all_fields = []
        for chunk in chunks:
            # Build content blocks with page images
            content_blocks = [p.to_claude_content() for p in chunk]
            page_range = f"{chunk[0].page_number}-{chunk[-1].page_number}"

            deal_context = {"document_type": document_type, "filename": doc.filename}
            task_data = {"page_images": content_blocks, "page_range": page_range}

            try:
                llm_result = await _ctx.llm_client.execute(
                    prompt_name, deal_context, task_data,
                    db=db, deal_id=_ctx.deal_id,
                )
                raw_fields = llm_result.get("fields", {})
                if isinstance(raw_fields, dict):
                    all_fields.extend(
                        {"field_name": k, **v} for k, v in raw_fields.items()
                    )
                else:
                    all_fields.extend(raw_fields)
            except Exception as exc:
                logger.warning("Extraction failed for chunk pages %s: %s", page_range, exc)

        # Create ExtractedValue records with confidence scoring
        created_count = 0
        for raw_field in all_fields:
            field_name = raw_field.get("field_name")
            value = raw_field.get("value")
            if not field_name:
                continue

            confidence_score, confidence_basis = score_confidence(raw_field)
            flag = assign_flag(confidence_score)

            ev = ExtractedValue(
                deal_id=_ctx.deal_id,
                field_name=field_name,
                value=str(value) if value is not None else None,
                source_doc_id=doc_uuid,
                source_page=raw_field.get("source_page"),
                source_text_snippet=raw_field.get("source_text", "")[:500],
                confidence_score=confidence_score,
                confidence_basis=confidence_basis,
                extraction_method="agent_pdf_vision",
                flag=flag,
            )
            db.add(ev)
            created_count += 1

        await db.flush()

        return ToolResult(data={
            "document_id": document_id,
            "document_type": document_type,
            "fields_extracted": created_count,
            "chunks_processed": len(chunks),
            "total_pages": len(pages),
        })


class ExtractFromExcelTool(PlumbTool):
    name = "extract_from_excel"
    description = "Extract structured data from an Excel file using openpyxl parsing."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "document_id": {"type": "string", "description": "UUID of the Excel document"},
            },
            "required": ["document_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, document_id: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db or not _ctx.llm_client:
            return ToolResult(success=False, error="ToolContext with db and llm_client required")

        from app.extraction.confidence import assign_flag, score_confidence
        from app.extraction.handlers import get_prompt_name
        from app.models.document import Document
        from app.models.extraction import ExtractedValue
        from app.parsing.excel import extract_excel_content, format_sheets_for_llm
        from app.storage.s3 import download_document

        db: AsyncSession = _ctx.db
        doc_uuid = uuid.UUID(document_id)

        result = await db.execute(select(Document).where(Document.id == doc_uuid))
        doc = result.scalar_one_or_none()
        if not doc:
            return ToolResult(success=False, error=f"Document {document_id} not found")

        doc_type = doc.document_type or "pro_forma"
        prompt_name = get_prompt_name(doc_type)
        if not prompt_name:
            return ToolResult(success=False, error=f"No extraction prompt for document type: {doc_type}")

        # Download and parse Excel
        file_bytes = await asyncio.to_thread(download_document, doc.s3_key)
        excel_content = await asyncio.to_thread(extract_excel_content, file_bytes)
        formatted = format_sheets_for_llm(excel_content)

        deal_context = {"document_type": doc_type, "filename": doc.filename}
        task_data = {"sheet_text": formatted, "sheet_names": excel_content.sheet_names}

        llm_result = await _ctx.llm_client.execute(
            prompt_name, deal_context, task_data,
            db=db, deal_id=_ctx.deal_id,
        )

        raw_fields = llm_result.get("fields", {})
        if isinstance(raw_fields, dict):
            fields = [{"field_name": k, **v} for k, v in raw_fields.items()]
        else:
            fields = raw_fields
        created_count = 0
        for raw_field in fields:
            field_name = raw_field.get("field_name")
            value = raw_field.get("value")
            if not field_name:
                continue

            # Excel extractions get higher base confidence (structured data)
            raw_field.setdefault("source_type", "table_cell")
            raw_field.setdefault("label_match", "exact")
            confidence_score, confidence_basis = score_confidence(raw_field)
            flag = assign_flag(confidence_score)

            ev = ExtractedValue(
                deal_id=_ctx.deal_id,
                field_name=field_name,
                value=str(value) if value is not None else None,
                source_doc_id=doc_uuid,
                source_text_snippet=raw_field.get("source_text", "")[:500],
                confidence_score=confidence_score,
                confidence_basis=confidence_basis,
                extraction_method="agent_excel",
                flag=flag,
            )
            db.add(ev)
            created_count += 1

        await db.flush()

        return ToolResult(data={
            "document_id": document_id,
            "document_type": doc_type,
            "fields_extracted": created_count,
            "sheet_names": excel_content.sheet_names,
        })


class RunCrossReferencesTool(PlumbTool):
    name = "run_cross_references"
    description = "Run cross-reference consistency checks across all extracted values for a deal."
    permission = ToolPermission.AUTO

    def get_input_schema(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "deal_id": {"type": "string", "description": "UUID of the deal"},
            },
            "required": ["deal_id"],
        }

    async def execute(self, _ctx: ToolContext | None = None, deal_id: str = "", **kwargs) -> ToolResult:
        if not _ctx or not _ctx.db:
            return ToolResult(success=False, error="ToolContext with db required")

        from app.db.session import sync_session_factory
        from app.extraction.cross_references import run_all_cross_references

        deal_uuid = uuid.UUID(deal_id) if deal_id else _ctx.deal_id
        if not deal_uuid:
            return ToolResult(success=False, error="deal_id required")

        # Cross-reference engine uses sync SQLAlchemy — run in thread
        def _run_sync():
            sync_db = sync_session_factory()
            try:
                results = run_all_cross_references(deal_uuid, sync_db)
                sync_db.commit()
                return results
            except Exception:
                sync_db.rollback()
                raise
            finally:
                sync_db.close()

        xrefs = await asyncio.to_thread(_run_sync)

        summary = {"match": 0, "mismatch": 0, "within_tolerance": 0, "unable_to_check": 0}
        details = []
        for xref in xrefs:
            summary[xref.result] = summary.get(xref.result, 0) + 1
            if xref.result in ("mismatch", "within_tolerance"):
                details.append({
                    "rule": xref.rule_name,
                    "result": xref.result,
                    "field_a": xref.field_a,
                    "field_a_value": xref.field_a_value,
                    "field_b": xref.field_b,
                    "field_b_value": xref.field_b_value,
                    "delta": xref.delta,
                })

        return ToolResult(data={
            "deal_id": str(deal_uuid),
            "total_checks": len(xrefs),
            "summary": summary,
            "issues": details,
        })
