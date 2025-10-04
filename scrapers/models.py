from datetime import datetime
from re import S
from turtle import st
from typing import List, Optional

from pydantic import BaseModel


class Track(BaseModel):
    name: str
    artist: str
    album: Optional[str] = None

class Episode(BaseModel):
    id: Optional[str] = None
    date: datetime
    tracks: List[Track] = []



