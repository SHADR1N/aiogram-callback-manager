import asyncio
import os
import random
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup
from aiogram_callback_manager import AsyncCallbackManager

API_TOKEN = os.environ['API_TOKEN']

bot = Bot(token=API_TOKEN)
dp = Dispatcher()
callback_manager = AsyncCallbackManager(use_json=False)
dp.include_router(callback_manager.router)
asyncio.get_event_loop().run_until_complete(callback_manager.init_db())

class Product:
    def __init__(self, name: str, price: int):
        self.name = name
        self.price = price

    def __str__(self):
        return self.name

products = [Product(name=f"Товар {i}", price=random.randint(100, 1000000)) for i in range(1, 101)]

@callback_manager.callback_handler()
async def product_list(callback_query: types.CallbackQuery, page: int = 1):
    pagination_buttons = await callback_manager.create_buttons(products, product_list, product_detail, page=page)
    keyboard = InlineKeyboardMarkup(inline_keyboard=pagination_buttons)
    await callback_query.message.edit_text(text=f"Страница {page}", reply_markup=keyboard)

@callback_manager.callback_handler()
async def product_detail(callback_query: types.CallbackQuery, element: Product):
    await callback_query.answer(f"Вы выбрали {element.name} ценой {element.price}")

@dp.message(Command('start'))
async def start_command(message: types.Message):
    btn=await callback_manager.create_button('Товары',product_list)
    await message.answer('Меню',reply_markup=InlineKeyboardMarkup(inline_keyboard=[[btn]]))

if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
