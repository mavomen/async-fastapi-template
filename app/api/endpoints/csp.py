import json

import structlog
from fastapi import APIRouter, Request, Response

logger = structlog.get_logger("app.csp")

router = APIRouter()


@router.post(
    "/csp-report",
    include_in_schema=False,
)
async def receive_csp_report(request: Request) -> Response:
    body = await request.body()
    if body:
        try:
            report = json.loads(body)
            logger.warning("csp_violation", report=report)
        except json.JSONDecodeError:
            logger.warning("csp_violation_invalid_json")
    return Response(status_code=204)
