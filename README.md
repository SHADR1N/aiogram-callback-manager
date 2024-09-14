# aiogram-callback-manager
Асинхронный менеджер callback-данных для aiogram, облегчающий создание динамических клавиатур и управление обратными вызовами с сохранением состояния между вызовами.

# Особенности
Упрощенная обработка callback_data: Легко создавать кнопки с обработчиками без необходимости вручную управлять callback_data.
Поддержка пагинации: Встроенные функции для создания пагинированных списков с навигацией.
Хранение состояния: Автоматическое сохранение и загрузка состояния между вызовами, используя SQLite (или другое хранилище).
Динамические кнопки: Создание кнопок на основе списков объектов, с автоматической передачей текущего элемента в обработчик.
Поддержка "Назад" кнопок: Возможность добавить кнопку "Назад" для возврата к предыдущему меню.
# Установка

`pip install aiogram-callback-manager`
# Быстрый старт
## Инициализация менеджера
```from aiogram import Bot, Dispatcher
from aiogram_callback_manager import AsyncCallbackManager

API_TOKEN = 'ВАШ_ТОКЕН_ТЕЛЕГРАМ_БОТА'

bot = Bot(token=API_TOKEN)
dp = Dispatcher()

#Инициализация менеджера callback
callback_manager = AsyncCallbackManager(use_json=False)

#Включение роутера менеджера в диспетчер
dp.include_router(callback_manager.router)

#Инициализация базы данных (не забудьте вызвать это перед началом обработки)
await callback_manager.init_db()
# Создание обработчиков с использованием декоратора @callback_manager.callback_handler()
from aiogram import types

# Определение обработчика для кнопки
@callback_manager.callback_handler()
async def show_message(callback_query: types.CallbackQuery, message: str):
    await callback_query.message.edit_text(f"Вы выбрали: {message}")`
# Создание кнопки и отправка сообщения с клавиатурой

from aiogram.types import InlineKeyboardMarkup

# Создание кнопки, которая вызовет обработчик `show_message` с аргументом `message`
button = await callback_manager.create_button(
    text="Нажми меня",
    func=show_message,
    message="Привет, мир!"
)

# Создание клавиатуры и отправка сообщения
keyboard = InlineKeyboardMarkup(inline_keyboard=[[button]])
await message.answer("Выберите опцию:", reply_markup=keyboard) 
```

# Пагинация и динамические кнопки
## Описание
Метод create_buttons позволяет создавать список кнопок на основе переданного списка объектов. Он автоматически обрабатывает пагинацию и передает текущий выбранный элемент в обработчик под именем element.