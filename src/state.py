from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, TypedDict, Optional, Tuple

class ChatMessage(TypedDict):
    role: str
    content: str

@dataclass
class InMemoryChatStore:
    """Простейшее in-memory хранилище истории сообщений по user_id.
    Для продакшена замените на БД/кэш (Redis, Postgres)."""
    by_user: Dict[int, List[ChatMessage]] = field(default_factory=dict)
    max_messages: int = 16  # хранить последние N сообщений (system не считаем)

    def get(self, user_id: int) -> List[ChatMessage]:
        return self.by_user.get(user_id, [])

    def set(self, user_id: int, messages: List[ChatMessage]) -> None:
        # Обрезаем историю, чтобы она не разрасталась
        self.by_user[user_id] = messages[-self.max_messages :]

    def reset(self, user_id: int) -> None:
        self.by_user.pop(user_id, None)

# Глобальный инстанс простого стора
store = InMemoryChatStore()


# ---------------------------
# Простейшее состояние формы
# ---------------------------

class FormStep:
    INTERESTS = "INTERESTS"
    TIME = "TIME"
    LOCATION = "LOCATION"
    DONE = "DONE"


class FormData(TypedDict, total=False):
    interests: str
    time_hours: float
    location_text: str
    location_coords: Tuple[float, float]


@dataclass
class FormSession:
    step: str = FormStep.INTERESTS
    data: FormData = field(default_factory=dict)


@dataclass
class InMemoryFormStore:
    by_user: Dict[int, FormSession] = field(default_factory=dict)
    seen_users: set[int] = field(default_factory=set)

    def get(self, user_id: int) -> Optional[FormSession]:
        return self.by_user.get(user_id)

    def start(self, user_id: int) -> FormSession:
        session = FormSession()
        self.by_user[user_id] = session
        return session

    def set_step(self, user_id: int, step: str) -> None:
        session = self.by_user.get(user_id)
        if not session:
            session = self.start(user_id)
        session.step = step
        self.by_user[user_id] = session

    def update_data(self, user_id: int, **kwargs) -> None:
        session = self.by_user.get(user_id)
        if not session:
            session = self.start(user_id)
        session.data.update(kwargs)  # type: ignore[arg-type]
        self.by_user[user_id] = session

    def reset(self, user_id: int) -> None:
        self.by_user.pop(user_id, None)

    def mark_seen(self, user_id: int) -> None:
        self.seen_users.add(user_id)

    def has_seen(self, user_id: int) -> bool:
        return user_id in self.seen_users


form_store = InMemoryFormStore()
