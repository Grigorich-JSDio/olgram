"""
Здесь работа с ботами на первом уровне вложенности: список ботов, добавление ботов
"""
from aiogram import types, Bot as AioBot
from aiogram.dispatcher import FSMContext
from aiogram.utils.exceptions import Unauthorized, TelegramAPIError
from tortoise.exceptions import IntegrityError
import re
from textwrap import dedent

from olgram.models.models import Bot, User
from olgram.settings import OlgramSettings
from olgram.commands.menu import send_bots_menu

from olgram.router import dp

token_pattern = r'[0-9]{8,10}:[a-zA-Z0-9_-]{35}'


@dp.message_handler(commands=["mybots"], state="*")
async def my_bots(message: types.Message, state: FSMContext):
    """
    Команда /mybots (список ботов)
    """
    return await send_bots_menu(message.chat.id, message.from_user.id)


@dp.message_handler(commands=["addbot"], state="*")
async def add_bot(message: types.Message, state: FSMContext):
    """
    Команда /addbot (добавить бота)
    """
    bot_count = await Bot.filter(owner__telegram_id=message.from_user.id).count()
    if bot_count >= OlgramSettings.max_bots_per_user():
        await message.answer("У вас уже слишком много ботов.")
        return

    await message.answer(dedent("""
    Чтобы подключить бот, вам нужно выполнить три действия:

    1. Перейдите в бот @BotFather, нажмите START и отправьте команду /newbot
    2. Введите название бота, а потом username бота.
    3. После создания бота перешлите ответное сообщение в этот бот или скопируйте и пришлите token бота.
    
    Важно: не подключайте боты, которые используются в других сервисах (Manybot, Chatfuel, Livegram и других).
    
    Подробную инструкцию по созданию бота читайте здесь /help)
    """))
    await state.set_state("add_bot")


@dp.message_handler(state="add_bot", content_types="text", regexp="^[^/].+")  # Not command
async def bot_added(message: types.Message, state: FSMContext):
    """
    Пользователь добавляет бота и мы ждём от него токен
    """
    token = re.findall(token_pattern, message.text)

    async def on_invalid_token():
        await message.answer(dedent("""
        Это не токен бота. 

        Токен выглядит вот так: 123456789:AAAA-abc123_AbcdEFghijKLMnopqrstu12
        """))

    async def on_dummy_token():
        await message.answer(dedent("""
        Не удалось запустить этого бота: неверный токен
        """))

    async def on_unknown_error():
        await message.answer(dedent("""
        Не удалось запустить этого бота: непредвиденная ошибка
        """))

    async def on_duplication_bot():
        await message.answer(dedent("""
        Такой бот уже есть в базе данных
        """))

    if not token:
        return await on_invalid_token()

    token = token[0]

    try:
        test_bot = AioBot(token)
        test_bot_info = await test_bot.get_me()
        await test_bot.session.close()
    except ValueError:
        return await on_invalid_token()
    except Unauthorized:
        return await on_dummy_token()
    except TelegramAPIError:
        return await on_unknown_error()

    user, _ = await User.get_or_create(telegram_id=message.from_user.id)
    bot = Bot(token=token, owner=user, name=test_bot_info.username, super_chat_id=message.from_user.id)
    try:
        await bot.save()
    except IntegrityError:
        return await on_duplication_bot()

    await message.answer("Бот добавлен!")
    await state.reset_state()