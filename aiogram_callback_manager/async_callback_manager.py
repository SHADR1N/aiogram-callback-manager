import asyncio
import functools
import inspect
import traceback
import uuid
from dataclasses import is_dataclass, asdict
from math import ceil

from aiogram import Router, types
from aiogram.dispatcher.event.handler import FilterObject
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from functools import wraps
import pickle
import hashlib
import time
import json
from typing import Any, Callable, Dict, Optional, List, Union

from .base_db_storage import SQLiteStorage, CallbackDataStorage
from .logger import logger
from .messages import MockMessage


class AsyncCallbackManager:
    def __init__(
            self,
            use_json: bool = False,
            storage: CallbackDataStorage = None
    ):
        """
              Инициализация менеджера асинхронных callback'ов.

              :param use_json: Использовать JSON для сериализации данных.
              :param storage: Экземпляр хранилища для callback данных.
        """
        if storage is None:
            if use_json is True:
                storage = SQLiteStorage('json_callback_data.db')
            else:
                storage = SQLiteStorage('pickle_callback_data.db')

        self.router = Router()
        self.use_json = use_json
        self._handlers = {}
        self.storage = storage

        # Регистрация основного хендлера
        self.router.callback_query.register(
            self.main_callback_handler,
            lambda c: c.data and c.data.startswith("cb_")
        )

        async def noop_callback(callback_query: CallbackQuery):
            await callback_query.answer()

        self.router.callback_query.register(noop_callback, lambda c: c.data == "noop")
        asyncio.get_event_loop().run_until_complete(self.init_db())

    async def init_db(self):
        await self.storage.init_db()

    async def _save_callback_data(self, data: Dict[str, Any], user_id: int) -> str:
        # Сериализация данных
        if self.use_json:
            if is_dataclass(data):
                data = asdict(data)
            data_bytes = json.dumps(data, ensure_ascii=False).encode()
        else:
            data_bytes = pickle.dumps(data)

        # Создание хэша длиной 64 символа
        data_hash = hashlib.md5(data_bytes).hexdigest()
        timestamp = time.time()

        # Сохранение в базу данных
        await self.storage.save(data_hash, data_bytes, timestamp, user_id)
        return data_hash

    async def _load_callback_data(self, data_hash: str, user_id: int) -> Optional[Dict[str, Any]]:
        data_bytes = await self.storage.load(data_hash, user_id)
        if data_bytes is not None:
            if self.use_json:
                data = json.loads(data_bytes.decode())
            else:
                data = pickle.loads(data_bytes, encoding="utf-8")
            return data
        return None

    async def clean_old_callback_data(self, expiry_time: int = 3600):
        # Удаление записей старше expiry_time секунд
        current_time = time.time()
        return await self.storage.clean_old(expiry_time)

    async def main_callback_handler(self, callback_query: CallbackQuery, callback_data=None, *args):
        logger.debug(f"New request with callback data \"{callback_query.data}\"")

        if not callback_data:
            callback_data = callback_query.data

        if not callback_data.startswith("cb_"):
            return  # Не обрабатываем callback_data, не относящиеся к нашему модулю

        data_hash = callback_data[3:]  # Убираем префикс "cb_"
        # Загрузка данных из базы по хэшу
        data = await self._load_callback_data(data_hash, callback_query.from_user.id)
        if data is None:
            await callback_query.answer(MockMessage.DataInvalid, show_alert=True)
            return

        handler_id = data.get('handler_id')
        handler = self._handlers.get(handler_id)

        if handler is None:
            await callback_query.answer(MockMessage.HandlerNotFound, show_alert=True)
            return

        # Получение аргументов
        args = data.get('args', [])
        kwargs = data.get('kwargs', {})
        back_btn_data = data.get('back_btn')

        # Вызов обработчика
        try:
            t = inspect.signature(handler)
            if back_btn_data and 'back_btn' in t.parameters:
                kwargs['back_btn'] = InlineKeyboardButton(text='Назад', callback_data=back_btn_data)
            await handler(callback_query, *args, **kwargs)
        except Exception as _:
            traceback.print_exc()
            await callback_query.answer(MockMessage.RequestProcessingError, show_alert=True)

    def register_handler(self, func: Callable):
        handler_id = self._generate_handler_id(func)
        func.handler_id = handler_id
        self._handlers[handler_id] = func
        return func

    def callback_handler(self):
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(callback_query: CallbackQuery, *filters, **kwargs):
                await func(callback_query, *filters, **kwargs)

            # Генерируем уникальный идентификатор для обработчика
            handler_id = self._generate_handler_id(func)
            wrapper.handler_id = handler_id

            # Сохраняем обработчик в словаре с использованием handler_id
            self._handlers[handler_id] = wrapper
            logger.debug(f"Register new callback handler is {func.__name__}")
            return wrapper

        return decorator

    def _generate_handler_id(self, func_name: Callable):
        if not isinstance(func_name, str):
            func_name = func_name.__name__
        return hashlib.md5(func_name.encode()).hexdigest()

    @staticmethod
    def _extract_user_id(user_data):
        if not user_data:
            raise TypeError("Not implemented type")
        if isinstance(user_data, int):
            return user_data
        elif isinstance(user_data, (types.Message, types.CallbackQuery)):
            return user_data.from_user.id
        raise TypeError("Not implemented type")

    @staticmethod
    def _extract_callback_data(back_btn):
        if not back_btn:
            return None
        if isinstance(back_btn, str):
            return back_btn
        if isinstance(back_btn, InlineKeyboardButton):
            return back_btn.callback_data
        if isinstance(back_btn, types.Message):
            return back_btn.text
        if isinstance(back_btn, types.CallbackQuery):
            return back_btn.data
        raise TypeError("Not implemented type")

    async def create_button(
            self,
            text: str,
            func: Union[str, Callable],
            user_data: Union[int, types.Message | types.CallbackQuery],
            back_btn: Optional[str | types.CallbackQuery | types.Message | InlineKeyboardButton] = None,
            *args,
            **kwargs
    ) -> InlineKeyboardButton:
        """
              Создает InlineKeyboardButton с обработчиком.

              :param text: Текст на кнопке.
              :param func: Функция-обработчик или ее имя.
              :param user_data: ID пользователя телеграм
              :param back_btn: Кнопка "Назад" или данные для нее.
              :return: Экземпляр InlineKeyboardButton.
        """
        args = [asdict(arg) if is_dataclass(arg) else arg for arg in args]
        kwargs = {key: asdict(value) if is_dataclass(value) else value for key, value in kwargs.items()}

        data = {
            'handler_id': self._generate_handler_id(func if isinstance(func, str) else func.__name__),
            'args': args,
            'kwargs': kwargs,
            'back_btn': self._extract_callback_data(back_btn),
        }
        data_hash = await self._save_callback_data(data, self._extract_user_id(user_data))
        callback_data = f"cb_{data_hash}"
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    async def create_buttons(
            self,
            objects: List,
            display_func: Callable,
            button_func: Callable,
            user_data: Union[int, types.Message | types.CallbackQuery],
            text_func: Callable = str,
            objects_per_page=5,
            page=1,
            row=False,
            back_btn: Optional[str | CallbackQuery | types.Message] = None,
            *args,
            **kwargs
    ) -> List[InlineKeyboardButton]:
        keyboards = []

        current_objects = objects[(page - 1) * objects_per_page:page * objects_per_page]
        pagination_buttons = asyncio.create_task(
            self.create_paginate_buttons(
                func=display_func,
                total_pages=ceil(len(objects) / objects_per_page),
                current_page=page,
                back_btn=back_btn,
                user_data=user_data,
                *args,
                **kwargs
            )
        )

        tasks = []
        for obj in current_objects:
            kwargs_copy = kwargs.copy()
            kwargs_copy['element'] = obj
            tasks.append(
                asyncio.create_task(
                    self.create_button(
                        text=text_func(obj),
                        func=button_func,
                        back_btn=back_btn,
                        user_data=user_data,
                        *args,
                        **kwargs_copy
                    )
                )
            )

        buttons = await asyncio.gather(*tasks)
        for btn in buttons:
            elem = [btn] if not row else btn
            keyboards.append(elem)

        keyboards.append(await pagination_buttons)
        return keyboards

    async def create_paginate_buttons(
            self,
            *args,
            func: Callable,
            total_pages: int,
            current_page: int,
            user_data: Union[int, types.Message | types.CallbackQuery],
            back_btn: Optional[str] = None,
            max_buttons=5,
            **kwargs
    ) -> List[InlineKeyboardButton]:
        buttons = []

        # Определяем диапазон страниц для отображения
        max_buttons = min(max_buttons, total_pages)
        half_range = max_buttons // 2
        start_page = max(1, current_page - half_range)
        end_page = min(total_pages, current_page + half_range)
        if end_page - start_page < max_buttons:
            if current_page - half_range <= 0:
                end_page += max_buttons - (end_page - start_page) - 1
            if current_page + half_range > total_pages:
                start_page -= max_buttons - (end_page - start_page) - 1

        # Генерируем кнопки страниц
        for page in range(start_page, end_page + 1):
            if page == current_page:
                # Текущая страница
                buttons.append(InlineKeyboardButton(text=f"•{page}•", callback_data="noop"))
            else:
                kwargs_copy = kwargs.copy()
                kwargs_copy['page'] = page
                if back_btn is not None:
                    kwargs_copy['back_btn'] = back_btn  # Передаём back_btn в kwargs

                page_button = await self.create_button(
                    text=str(page),
                    func=func,
                    user_data=user_data,
                    *args,
                    **kwargs_copy
                )
                buttons.append(page_button)

        return buttons
