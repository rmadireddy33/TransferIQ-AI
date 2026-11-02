from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse


class UploadBodyLimit:
    """Cap multipart transport before parsing, including chunked requests."""
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST" or not scope["path"].endswith("/documents"):
            return await self.app(scope, receive, send)
        limit = scope["app"].state.settings.max_document_bytes + 256 * 1024
        detail = {"code": "document_too_large", "message": "Multipart request exceeds upload limit"}
        length = dict(scope["headers"]).get(b"content-length")
        if length and (not length.isdigit() or int(length) > limit):
            return await JSONResponse(status_code=413, content={"detail": detail})(scope, receive, send)
        seen = 0

        async def limited_receive():
            nonlocal seen
            message = await receive()
            seen += len(message.get("body", b""))
            if seen > limit:
                raise HTTPException(413, detail=detail)
            return message
        await self.app(scope, limited_receive, send)
