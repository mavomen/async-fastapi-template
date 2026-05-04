from io import BytesIO

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_upload_and_download_flow(
    async_client: AsyncClient, auth_headers: dict, db_session: AsyncSession
):
    file_content = b"Integration upload test"
    files = {"file": ("flow.txt", BytesIO(file_content), "text/plain")}
    upload_resp = await async_client.post("/api/v1/files/upload", files=files, headers=auth_headers)
    assert upload_resp.status_code == 201
    path = upload_resp.json()["path"]

    download_resp = await async_client.get(f"/api/v1/files/download/{path}", headers=auth_headers)
    assert download_resp.status_code == 200
    assert download_resp.content == file_content
