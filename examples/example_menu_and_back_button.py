import asyncio
import dataclasses
import functools
import os
import random
from typing import List

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv

from aiogram_callback_manager import AsyncCallbackManager


load_dotenv()
API_TOKEN = os.environ['API_TOKEN']

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

# Инициализация менеджера обратных вызовов
callback_manager = AsyncCallbackManager(use_json=False)

# Регистрация внутреннего роутера менеджера
dp.include_router(callback_manager.router)


class Product:
    def __init__(self,name:str,price:int):
        self.name=name
        self.price=price
        self.shop=None
    def __str__(self):
        return self.name

class Shop:
    def __init__(self,name:str,products:List[Product]):
        self.name=name
        self.products=products
        for product in products:
            product.shop=self
    def __str__(self):
        return self.name


# Пример данных
products =lambda :[Product(name=f"Товар {i}",price=random.randint(100,1000000)) for i in range(1, 41)]  # Список из 100 товаров
shops= [Shop(name=f"Магазин {i}",products=products()) for i in range(1, 21)]


# Обработчик списка товаров с пагинацией
@callback_manager.callback_handler()
async def product_list(callback_query: types.CallbackQuery, element: Shop,page: int = 1,back_btn=None):
    product_list_partial = functools.partial(product_list, element=element)
    product_list_partial = callback_manager.register_handler(product_list_partial)


    pagination_buttons = await callback_manager.create_buttons(element.products,product_list_partial,product_detail,back_btn= callback_query,page=page)
    if back_btn:
        pagination_buttons.append([back_btn])
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=pagination_buttons)


    await callback_query.message.edit_text(
        text=f"Страница {page} Магазина",
        reply_markup=keyboard
    )

@callback_manager.callback_handler()
async def shop_list(callback_query: types.CallbackQuery, page: int = 1,back_btn=None):
    #print(back_btn)
    pagination_buttons = await callback_manager.create_buttons(shops,shop_list,product_list,page=page,back_btn= callback_query)
    if back_btn:
        pagination_buttons.append([back_btn])
    # Создаем клавиатуру
    keyboard = InlineKeyboardMarkup(inline_keyboard=pagination_buttons)

    # Отправляем сообщение или редактируем существующее

    if callback_query.message:
        await callback_query.message.edit_text(
            text=f"Магазины",
            reply_markup=keyboard
        )

@callback_manager.callback_handler()
async def product_remove(callback_query: types.CallbackQuery, product: Product, back_btn: InlineKeyboardButton):
    shop=product.shop
    shop.products.remove(product)
    await callback_query.answer('Удалил')

    # Возвращаемся к списку товаров магазина
    back_data = back_btn.callback_data
    await callback_manager.main_callback_handler(callback_query, back_data)


@callback_manager.callback_handler()
async def product_detail(callback_query: types.CallbackQuery, element: Product, back_btn):
    await callback_query.message.edit_text(
        f"Вы выбрали {element.name} ценой {element.price}",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[back_btn]]
        )
    )


@dp.message(Command('start'))
@dp.callback_query(lambda x:x.data=='/start')
async def start_command(event: types.Message | types.CallbackQuery):
    # Начинаем с первой страницы
    button = await callback_manager.create_button(
            text="Магазины",
            func=shop_list,
            back_btn=event
        )
    func=event.message.edit_text if isinstance(event, types.CallbackQuery) else event.answer
    await func('Меню:', reply_markup=InlineKeyboardMarkup(inline_keyboard=[[button]]))


# Запуск бота
if __name__ == '__main__':
    asyncio.run(dp.start_polling(bot))
