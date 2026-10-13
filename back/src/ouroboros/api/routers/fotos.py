from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from ouroboros.api.deps import Session
from ouroboros.core.media_store import MediaStore
from ouroboros.models.foto import PoliticoFoto

router = APIRouter(prefix="/fotos", tags=["fotos"])


@router.get(
    "/{foto_id}",
    summary="Arquivo da foto",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}, 304: {}, 404: {}},
)
async def obter_foto(foto_id: int, request: Request, session: Session) -> Response:
    foto = await session.get(PoliticoFoto, foto_id)
    if foto is None:
        raise HTTPException(status_code=404, detail="foto não encontrada")
    path = MediaStore().path_for(foto.sha256, foto.extensao)
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo da foto não está disponível")
    etag = f'"{foto.sha256}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type=foto.content_type, headers=headers)
