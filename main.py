from aiogram import *
from rich.progress import *

import config
import telegram
import sqlite3
import asyncio
import logging
import threading
from threading import Thread
from aiogram.utils import markdown as md
from typing import Awaitable
from aiogram import Bot, Dispatcher, executor, types
from datetime import datetime, timedelta
from aiogram.dispatcher import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.types import Message
from aiogram.types import CallbackQuery
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.utils.exceptions import Throttled
from aiogram.utils.helper import Helper, HelperMode, ListItem
from rich.console import Console
from rich.progress import *

ADMIN = #ваш телеграм айди

logging.basicConfig(level=logging.INFO)

storage = MemoryStorage()

bot = Bot(token=config.token)

dp = Dispatcher(bot, storage=storage)

async def anti_flood(*args, **kwargs):
    m = args[0]
    await m.answer("Хватит спамить!")

conn = sqlite3.connect('db.db')
cur = conn.cursor()
cur.execute("""CREATE TABLE IF NOT EXISTS users(
   user_id INTEGER,
   name TEXT,
   username TEXT,
   block INTEGER
);""")

class dialog(StatesGroup):
    spam = State()

async def add_user(user_id: int, name: str, username: str):
    cur.execute('INSERT INTO users(user_id, name, username, block) VALUES (?, ?, ?, ?)', (user_id, name, username, 0))
    profile_link = f'<a href="tg://user?id={user_id}">{name}</a>'
    await bot.send_message(ADMIN, f"Новый пользователь зарегистрировался в боте:\nИмя: {profile_link}", parse_mode='HTML')
    conn.commit()

@dp.message_handler(commands=['start'])
@dp.throttled(anti_flood,rate=3)
async def start(message: Message):
  cur = conn.cursor()
  cur.execute(f"SELECT block FROM users WHERE user_id = {message.chat.id}")
  result = cur.fetchone()
  if message.from_user.id == ADMIN:
    await message.answer('Введите команду /admin')
  else:
      if result is None:
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE user_id = ?', (message.from_user.id,))
        entry = cur.fetchone()
        if entry is None:
          await add_user(message.from_user.id, message.from_user.full_name, message.from_user.username)
          conn.commit()
          await bot.send_message(message.chat.id, f"Здравствуй, {message.from_user.first_name}.)
      else:
        await bot.send_message(message.chat.id, f"Здравствуй, {message.from_user.first_name}.)

@dp.message_handler(commands=['admin'])
async def admin(message: Message):
    cur = conn.cursor()
    cur.execute(f"SELECT block FROM users WHERE user_id = {message.chat.id}")
    result = cur.fetchone()
    if message.from_user.id == ADMIN:
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.InlineKeyboardButton(text="Отправить сообщение пользователям"))
        keyboard.add(types.InlineKeyboardButton(text='Статистика бота'))
        keyboard.add(types.InlineKeyboardButton(text='Назад', reply_markup=profile_keyboard))
        await message.answer(f'<pre>{message.from_user.first_name}</pre>, выберите действие👇', parse_mode="html", reply_markup=keyboard)
    else:
        if result is None:
            cur = conn.cursor()
            cur.execute(f'''SELECT * FROM users WHERE (user_id="{message.from_user.id}")''')
            entry = cur.fetchone()
            if entry is None:
                cur.execute(f'''INSERT INTO users VALUES ('{message.from_user.id}', '0')''')
            conn.commit()
            await message.answer('Вы не являетесь админом.')
        else:
            await message.answer('Вы не являетесь админом.')

@dp.message_handler(content_types=['text'], text='Статистика бота')
async def state(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN:
        cur = conn.cursor()
        cur.execute('''SELECT user_id, name, username FROM users''')
        results = cur.fetchall()
        if len(results) > 0:
            text = f'<b>👮‍♂️Количество пользователей в боте:</b> {len(results)}\n\n<b>Список пользователей:</b>\n'
            for user_id, name, username in results:
                if name != '0':
                    text += f'<a href="tg://user?id={user_id}">{name}'
                    if username:
                        text += f' (@{username})'
                    text += '</a>\n'
                else:
                    text += f'<a href="tg://user?id={user_id}">{user_id}'
                    if username:
                        text += f' (@{username})'
                    text += '</a>\n'
            if message.chat.type == 'private':
                await message.answer(text, parse_mode="HTML")
            else:
                await message.answer(text, parse_mode="HTML")
        else:
            await message.answer('В боте нет зарегистрированных пользователей.')
    else:
        await message.answer("Невозможно обновить статистику.")

@dp.message_handler(content_types=['text'], text='Отправить сообщение пользователям')
async def spam(message: Message):
    if message.from_user.id == ADMIN:
        await dialog.spam.set()
        await message.answer('Введите сообщение, которое получат все пользователи бота')
    else:
        await message.answer('Вы не являетесь админом')

@dp.message_handler(content_types=['text'], state=dialog.spam)
async def start_spam_text(message: Message, state: FSMContext):
    text = message.text
    if text == 'Назад':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.InlineKeyboardButton(text="Отправить сообщение пользователям"))
        keyboard.add(types.InlineKeyboardButton(text='Статистика бота'))
        keyboard.add(types.InlineKeyboardButton(text='Назад', reply_markup=back_keyboard))
        await message.answer('Главное меню', reply_markup=keyboard)
        await state.finish()
    else:
        cur = conn.cursor()
        cur.execute(f'''SELECT user_id FROM users''')
        spam_base = cur.fetchall()
        for z in range(len(spam_base)):
            await bot.send_message(spam_base[z][0], text)
        await message.answer(f'✅Сообщение отправлено!')
        await state.finish()

@dp.message_handler(content_types=['photo'], state=dialog.spam)
async def start_spam_photo(message: Message, state: FSMContext):
    photo_id = message.photo[-1].file_id
    if message.caption == 'Назад':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.InlineKeyboardButton(text="Отправить сообщение пользователям"))
        keyboard.add(types.InlineKeyboardButton(text='Статистика бота'))
        keyboard.add(types.InlineKeyboardButton(text='Назад', reply_markup=back_keyboard))
        await message.answer('Главное меню', reply_markup=keyboard)
        await state.finish()
    else:
        cur = conn.cursor()
        cur.execute(f'''SELECT user_id FROM users''')
        spam_base = cur.fetchall()
        for z in range(len(spam_base)):
            await bot.send_photo(spam_base[z][0], photo_id, caption=message.caption)
        await message.answer(f'✅Сообщение отправлено!')
        await state.finish()

@dp.message_handler(content_types=['video'], state=dialog.spam)
async def start_spam_video(message: Message, state: FSMContext):
    video_id = message.video.file_id
    if message.caption == 'Назад':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.InlineKeyboardButton(text="Отправить сообщение пользователям"))
        keyboard.add(types.InlineKeyboardButton(text='Статистика бота'))
        keyboard.add(types.InlineKeyboardButton(text='Назад', reply_markup=back_keyboard))
        await message.answer('Главное меню', reply_markup=keyboard)
        await state.finish()
    else:
        cur = conn.cursor()
        cur.execute(f'''SELECT user_id FROM users''')
        spam_base = cur.fetchall()
        for z in range(len(spam_base)):
            await bot.send_video(spam_base[z][0], video_id, caption=message.caption)
        await message.answer(f'✅Сообщение отправлено!')
        await state.finish()

@dp.message_handler(content_types=['voice'], state=dialog.spam)
async def start_spam_voice(message: Message, state: FSMContext):
    voice_id = message.voice.file_id
    if message.caption == 'Назад':
        keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
        keyboard.add(types.InlineKeyboardButton(text="Отправить сообщение пользователям"))
        keyboard.add(types.InlineKeyboardButton(text='Статистика бота'))
        keyboard.add(types.InlineKeyboardButton(text='Назад', reply_markup=back_keyboard))
        await message.answer('Главное меню', reply_markup=keyboard)
        await state.finish()
    else:
        cur = conn.cursor()
        cur.execute(f'''SELECT user_id FROM users''')
        spam_base = cur.fetchall()
        for z in range(len(spam_base)):
            await bot.send_voice(spam_base[z][0], voice_id, caption=message.caption)
        await message.answer(f'✅Сообщение отправлено!')
        await state.finish()
        
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
