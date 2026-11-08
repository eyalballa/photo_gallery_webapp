from datetime import datetime
from typing import Protocol

from pydantic import BaseModel, ConfigDict


class SourceItem(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str  # stable media id
    created: datetime  # when it was added to the album
    width: int
    height: int
    url: str  # source-specific locator handed back to `download`


class SourceListing(BaseModel):
    items: list[SourceItem]
    complete: bool  # False if the listing may be missing items; sync then skips removals


class PhotoSource(Protocol):
    id: str

    async def list_items(self) -> SourceListing: ...

    async def download(self, item: SourceItem, max_px: int) -> bytes: ...
