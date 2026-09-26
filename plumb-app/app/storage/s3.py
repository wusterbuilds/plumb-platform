import uuid

import boto3
from botocore.config import Config
from fastapi import UploadFile

from app.config import settings

MAX_UPLOAD_SIZE = 200 * 1024 * 1024  # 200 MB


class FileTooLargeError(Exception):
    pass


def _get_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.S3_ENDPOINT_URL,
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
        region_name=settings.S3_REGION,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket():
    client = _get_client()
    try:
        client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
    except client.exceptions.ClientError as e:
        error_code = int(e.response["Error"].get("Code", 0))
        if error_code == 404:
            client.create_bucket(Bucket=settings.S3_BUCKET_NAME)
        else:
            raise


def upload_document(deal_id: uuid.UUID, file: UploadFile) -> tuple[str, int]:
    client = _get_client()
    s3_key = f"deals/{deal_id}/documents/{file.filename}"

    content = file.file.read()
    file_size = len(content)
    if file_size > MAX_UPLOAD_SIZE:
        raise FileTooLargeError(
            f"File size {file_size} bytes exceeds maximum of {MAX_UPLOAD_SIZE} bytes"
        )
    file.file.seek(0)

    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=content,
        ContentType=file.content_type or "application/octet-stream",
    )
    return s3_key, file_size


def get_presigned_url(s3_key: str, expires_in: int = 3600, inline: bool = False) -> str:
    client = _get_client()
    params = {"Bucket": settings.S3_BUCKET_NAME, "Key": s3_key}
    if inline:
        params["ResponseContentDisposition"] = "inline"
        # Ensure browser renders PDFs inline rather than downloading
        if s3_key.lower().endswith(".pdf"):
            params["ResponseContentType"] = "application/pdf"
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )


def download_document(s3_key: str) -> bytes:
    """Download a document's raw bytes from S3."""
    client = _get_client()
    response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()


def delete_document(s3_key: str) -> None:
    client = _get_client()
    client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=s3_key)


def upload_bytes(data: bytes, s3_key: str, content_type: str = "application/octet-stream") -> str:
    client = _get_client()
    client.put_object(
        Bucket=settings.S3_BUCKET_NAME,
        Key=s3_key,
        Body=data,
        ContentType=content_type,
    )
    return s3_key
