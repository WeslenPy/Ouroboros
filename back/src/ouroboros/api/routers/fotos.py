from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response

from ouroboros.api.deps import Session
from ouroboros.core.media_store import MediaStore
from ouroboros.models.foto import ArquivoImagemMixin, PoliticoFoto

router = APIRouter(prefix="/fotos", tags=["fotos"])


@router.get(
    "/{foto_id}",
    summary="Arquivo da foto (fotos só com URL redirecionam para a fonte)",
    response_class=FileResponse,
    responses={200: {"content": {"image/jpeg": {}}}, 304: {}, 307: {}, 404: {}},
)
async def obter_foto(foto_id: int, request: Request, session: Session) -> Response:
    foto = await session.get(PoliticoFoto, foto_id)
    if foto is None:
        raise HTTPException(status_code=404, detail="foto não encontrada")
    return servir_imagem(foto, request)


def servir_imagem(imagem: ArquivoImagemMixin, request: Request) -> Response:
    """Arquivo do MediaStore com ETag; imagem só com URL redireciona para a origem."""
    if not imagem.armazenada:
        return RedirectResponse(imagem.url_origem, status_code=307)
    path = MediaStore().path_for(imagem.sha256, imagem.extensao)
    if not path.exists():
        raise HTTPException(status_code=404, detail="arquivo da imagem não está disponível")
    etag = f'"{imagem.sha256}"'
    headers = {"ETag": etag, "Cache-Control": "public, max-age=86400"}
    if request.headers.get("if-none-match") == etag:
        return Response(status_code=304, headers=headers)
    return FileResponse(path, media_type=imagem.content_type, headers=headers)
