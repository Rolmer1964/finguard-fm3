from typing import Any

import httpx
from fastapi import HTTPException, Request, Response
from fastapi.responses import StreamingResponse

HOP_BY_HOP = {
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host", "content-length",
}


async def forward(
    request: Request,
    target_base: str,
    target_path: str,
    *,
    user_claims: dict | None = None,
    timeout: float = 60.0,
) -> Response:
    url = f"{target_base.rstrip('/')}/{target_path.lstrip('/')}"

    fwd_headers: dict[str, str] = {}
    for k, v in request.headers.items():
        if k.lower() in HOP_BY_HOP or k.lower() == "authorization":
            continue
        fwd_headers[k] = v

    if user_claims:
        if "sub" in user_claims:
            fwd_headers["X-User-Id"] = str(user_claims["sub"])
        if "email" in user_claims:
            fwd_headers["X-User-Email"] = str(user_claims["email"])
        if "role" in user_claims:
            fwd_headers["X-User-Role"] = str(user_claims["role"])

    body = await request.body()

    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.request(
                request.method,
                url,
                params=dict(request.query_params),
                content=body,
                headers=fwd_headers,
            )
        except httpx.RequestError as exc:
            raise HTTPException(status_code=502, detail=f"Falha contatando serviço: {exc}") from exc

    out_headers = {k: v for k, v in resp.headers.items() if k.lower() not in HOP_BY_HOP}
    return Response(content=resp.content, status_code=resp.status_code, headers=out_headers, media_type=resp.headers.get("content-type"))
