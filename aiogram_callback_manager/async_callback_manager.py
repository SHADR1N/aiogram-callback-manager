import asyncio
import functools
import inspect
import traceback
import uuid
from dataclasses import is_dataclass, asdict
from math import ceil

from aiogram import Router, types
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from functools import wraps
import pickle
import hashlib
import time
import json
from typing import Any, Callable, Dict, Optional, List


from .base_db_storage import SQLiteStorage,CallbackDataStorage


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
        self.storage=storage

        # Регистрация основного хендлера
        self.router.callback_query.register(self.main_callback_handler, lambda c: c.data and c.data.startswith("cb_"))
        async def noop_callback(callback_query: CallbackQuery):
            await callback_query.answer()
        self.router.callback_query.register(noop_callback, lambda c: c.data == "noop")

    async def init_db(self):
        await self.storage.init_db()

    async def _save_callback_data(self, data: Dict[str, Any]) -> str:
        # Сериализация данных
        if self.use_json:
            if is_dataclass(data):
                data = asdict(data)
            data_bytes = json.dumps(data).encode()
        else:
            data_bytes = pickle.dumps(data)

        # Создание хэша длиной 64 символа
        data_hash =  hashlib.md5(data_bytes).hexdigest()
        timestamp = time.time()

        # Сохранение в базу данных
        await self.storage.save(data_hash,data_bytes,timestamp)
        return data_hash

    async def _load_callback_data(self, data_hash: str) -> Optional[Dict[str, Any]]:
        data_bytes=await self.storage.load(data_hash)
        if data_bytes:
            if self.use_json:
                data = json.loads(data_bytes.decode())
            else:
                data = pickle.loads(data_bytes)
            return data
        return None

    async def clean_old_callback_data(self, expiry_time: int = 3600):
        # Удаление записей старше expiry_time секунд
        current_time = time.time()
        return await self.storage.clean_old(expiry_time)

    async def main_callback_handler(self, callback_query: CallbackQuery,callback_data=None):
        if not callback_data :
            callback_data = callback_query.data

        if not callback_data.startswith("cb_"):
            return  # Не обрабатываем callback_data, не относящиеся к нашему модулю

        data_hash = callback_data[3:]  # Убираем префикс "cb_"
        # Загрузка данных из базы по хэшу
        data = await self._load_callback_data(data_hash)
        if data is None:
            await callback_query.answer("Данные устарели или недействительны.", show_alert=True)
            return

        handler_id = data.get('handler_id')
        handler = self._handlers.get(handler_id)
        if handler is None:
            await callback_query.answer("Обработчик не найден.", show_alert=True)
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
        except Exception as e:
            traceback.print_exc()
            await callback_query.answer("Произошла ошибка при обработке запроса.", show_alert=True)

    def register_handler(self, func: Callable):
        handler_id = str(uuid.uuid4())
        func.handler_id = handler_id
        self._handlers[handler_id] = func
        return func

    def callback_handler(self):
        def decorator(func: Callable):
            @wraps(func)
            async def wrapper(callback_query: CallbackQuery, *args, **kwargs):
                await func(callback_query, *args, **kwargs)

            # Генерируем уникальный идентификатор для обработчика
            handler_id = str(uuid.uuid4())
            wrapper.handler_id = handler_id

            # Сохраняем обработчик в словаре с использованием handler_id
            self._handlers[handler_id] = wrapper
            return wrapper

        return decorator
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

    async def create_button(self, text: str, func: Callable, back_btn: Optional[str|types.CallbackQuery|types.Message|InlineKeyboardButton] = None, *args,
                            **kwargs) -> InlineKeyboardButton:
        """
              Создает InlineKeyboardButton с обработчиком.

              :param text: Текст на кнопке.
              :param func: Функция-обработчик.
              :param back_btn: Кнопка "Назад" или данные для нее.
              :return: Экземпляр InlineKeyboardButton.
              """
        data = {
            'handler_id': getattr(func, 'handler_id', None),
            'args': args,
            'kwargs': kwargs,
            'back_btn': self._extract_callback_data(back_btn)
        }
        data_hash = await self._save_callback_data(data)
        callback_data = f"cb_{data_hash}"
        return InlineKeyboardButton(text=text, callback_data=callback_data)

    async def create_buttons(self, objects: List, display_func: Callable, button_func: Callable,
                             text_func: Callable = str, objects_per_page=5, page=1, row=False,
                             back_btn: Optional[str | CallbackQuery | types.Message] = None, *args,
                             **kwargs) -> InlineKeyboardMarkup:
        kb = []
        current_objects = objects[(page - 1) * objects_per_page:page * objects_per_page]
        paginat_btns = asyncio.create_task(
            self.create_paginate_buttons(display_func, ceil(len(objects) / objects_per_page), page, back_btn=back_btn, *args,
                                         **kwargs))
        tasks = []
        for obj in current_objects:
            kwargs_copy = kwargs.copy()
            kwargs_copy['element'] = obj
            tasks.append(asyncio.create_task(
                self.create_button(text_func(obj), button_func, back_btn=back_btn, *args, **kwargs_copy)))

        btns = await asyncio.gather(*tasks)
        for btn in btns:
            elem = [btn] if not row else btn
            kb.append(elem)
        kb.append(await paginat_btns)

        return kb

    async def create_paginate_buttons(self, func: Callable, total_pages: int, current_page: int,
                                      back_btn: Optional[str] = None, max_buttons = 5, *args, **kwargs) -> List[InlineKeyboardButton]:
        buttons = []

        # Определяем диапазон страниц для отображения
        max_buttons=min(max_buttons,total_pages)
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
                    *args,
                    **kwargs_copy
                )
                buttons.append(page_button)


        return buttons


