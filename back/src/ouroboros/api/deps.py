from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ouroboros.api.pagination import PageParams, page_params
from ouroboros.core.db import session_scope

Session = Annotated[AsyncSession, Depends(session_scope)]
Paging = Annotated[PageParams, Depends(page_params)]
