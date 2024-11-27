from dataclasses import dataclass, field
from typing import Optional

from aiogram.dispatcher.event.handler import HandlerObject


@dataclass
class _HandlerObject(HandlerObject):
    custom_kwargs: Optional[dict] = field(default_factory=dict)
