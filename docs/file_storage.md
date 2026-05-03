# File Storage Guide

The application supports both **local** and **S3** file storage backends.

## Configuration
Set `STORAGE_BACKEND` to `"local"` or `"s3"` via environment.

**Local:**
- `LOCAL_STORAGE_PATH` – directory for files (default `./uploads`)

**S3:**
- `S3_BUCKET`
- `S3_ENDPOINT_URL` (optional, for MinIO etc.)
- `S3_ACCESS_KEY`
- `S3_SECRET_KEY`
- `S3_REGION`

## Usage
- **Upload:** `POST /api/v1/files/upload` (multipart, authenticated)
- **Download:** `GET /api/v1/files/download/{path}` (authenticated)

## Implementation
- `app/storage/base.py` defines the abstract interface.
- `app/storage/local.py` and `app/storage/s3.py` implement it.
- A `get_storage` dependency injects the correct backend.
