import asyncio
import dataclasses
import logging
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup
from dotenv import load_dotenv

from aiogram_callback_manager import AsyncCallbackManager


load_dotenv()

API_TOKEN = os.environ['API_TOKEN']

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
callback_manager = AsyncCallbackManager(use_json=True)
dp.include_router(callback_manager.router)
asyncio.get_event_loop().run_until_complete(callback_manager.init_db())


@dataclasses.dataclass
class Product:
    name: str
    price: int


# Пример данных
products = [Product(name=f"Товар {i}", price=random.randint(100, 1000000)) for i in range(1, 101)]

@callback_manager.callback_handler()
async def product_list(callback_query: types.CallbackQuery, page: int = 1):
    items_per_page = 10
    total_pages = (len(products) + items_per_page - 1) // items_per_page
    page = max(1, min(page, total_pages))
    start_index = (page - 1) * items_per_page
    end_index = start_index + items_per_page
    current_products = products[start_index:end_index]

    buttons = [
        [
            await callback_manager.create_button(
                text=product.name,
                func=product_detail,
                product=product
            )
        ] for product in current_products
    ]
    pagination_buttons = await callback_manager.create_paginate_buttons(
        func=product_list,
        total_pages=total_pages,
        current_page=page,
        back_btn="Back to back"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons + [pagination_buttons])
    await callback_query.message.edit_text(text=f"Страница {page} из {total_pages}", reply_markup=keyboard)


@callback_manager.callback_handler()
async def product_detail(callback_query: types.CallbackQuery, product: Product):
    await callback_query.answer(f"Вы выбрали {product.name} ценой {product.price}")


@dp.message(Command('start'))
async def start_command(message: types.Message):
    btn = await callback_manager.create_button('Товары',product_list)
    await message.answer('Меню', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn]]))


if __name__ == '__main__':
    logging.getLogger("aiogram").setLevel(logging.DEBUG)
    asyncio.run(dp.start_polling(bot))
