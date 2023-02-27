import configparser
import logging
import cfg
import random
import sqlite3
import os
import tracemalloc
import time
import trigab

from trigab import trigger_words_b, trigger_words, rplist
from dotenv import load_dotenv
from cfg import AD_url, AD_name, AD_message
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Text
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ParseMode, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

print(os.listdir())

load_dotenv()
ball = 'ball.txt'
rusmat = 'list.txt'
ukrmat = 'ukr.txt'
logging.basicConfig(level=logging.INFO)
bot = Bot(token=os.getenv('TOKEN'))
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


# бот для рп
@dp.message_handler(lambda message: message.from_user is not None and
                                    any(word in message.text.lower() for word in trigger_words or trigger_words_b))
async def handle_message(message: types.Message):
    for word in trigger_words:
        if word in message.text.lower():
            inia = message.from_user.get_mention()
            initiator_mention = message.reply_to_message.from_user.get_mention()
            response = f"{inia}, {trigger_words[word]} {initiator_mention} {trigger_words_b[word]}"
            await message.answer(response, parse_mode=ParseMode.MARKDOWN)
            break


# для ню юз
@dp.message_handler(content_types=types.ContentType.NEW_CHAT_MEMBERS)
async def welcome_new_members(message: types.Message):
    for user in message.new_chat_members:
        await message.answer(f"<b>Добро пожаловать на завод, {user.full_name}!</b> \n"
                             f"Правила: https://t.me/factorychat_psk/104 \n"
                             f"\n"
                             f"{AD_message} \n"
                             f"<a href='https://projectkani.neyson.ru'>ProjectKani Community</a>",
                             parse_mode=ParseMode.HTML, disable_web_page_preview=True,
                             reply_markup=InlineKeyboardMarkup(
                                 inline_keyboard=[[InlineKeyboardButton(text=AD_name, url=AD_url)]]))


# мат бот
@dp.message_handler(commands=['mat_rus'])
async def rumat_handler(message: types.Message):
    # Открываем файл и читаем строки
    with open(rusmat, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    random_line = random.choice(lines)
    await message.reply(f"{random_line} \n"
                        f"{AD_message}", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=AD_name, url=AD_url)]]), parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['mat_ukr'])
async def ukrmat_handler(message: types.Message):
    # Открываем файл и читаем строки
    with open(ukrmat, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    random_line = random.choice(lines)
    await message.reply(f"{random_line} \n"
                        f"{AD_message}", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=AD_name, url=AD_url)]]), parse_mode=ParseMode.HTML)


# +-бот
class UserRating:
    def __init__(self, db_file):
        self.conn = sqlite3.connect(db_file)
        self.create_table()

    def create_table(self):
        c = self.conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY, rating INTEGER)''')
        self.conn.commit()

    def get_user_rating(self, user_id):
        c = self.conn.cursor()
        c.execute("SELECT rating FROM users WHERE user_id=?", (user_id,))
        res = c.fetchone()
        if res is not None:
            return res[0]
        return 0

    def update_user_rating(self, user_id, rating_change):
        current_rating = self.get_user_rating(user_id)
        new_rating = current_rating + rating_change
        c = self.conn.cursor()
        if current_rating == 0:
            c.execute("INSERT OR REPLACE INTO users (user_id, rating) VALUES (?, ?)", (user_id, new_rating))
        else:
            c.execute("UPDATE users SET rating=? WHERE user_id=?", (new_rating, user_id))
        self.conn.commit()


@dp.message_handler(commands=['rating'])
async def show_rating(message: types.Message):
    rating = UserRating('ratings.db')
    user_id = message.from_user.id
    user_rating = rating.get_user_rating(user_id)
    await message.answer(f"Твой рейтинг работника: {user_rating}")


@dp.message_handler(Text(['+', '-']), state=None)
async def process_rating(message: types.Message):
    rating = UserRating('ratings.db')
    user_id = message.reply_to_message.from_user.id
    if message.text == '+':
        rating_change = 1
    else:
        rating_change = -1
    rating.update_user_rating(user_id, rating_change)
    user_rating = rating.get_user_rating(user_id)
    await message.answer(f"Уровень доверия работника {message.reply_to_message.from_user.full_name}: {user_rating}")


class RatingStates(StatesGroup):
    waiting_for_rating = State()


@dp.message_handler(Text(['+', '-']), state=RatingStates.waiting_for_rating)
async def process_rating_with_reply(message: types.Message, state: FSMContext):
    rating = UserRating('ratings.db')
    user_id = state.get_data()['user_id']
    if message.text == '+':
        rating_change = 1
    else:
        rating_change = -1
    rating.update_user_rating(user_id, rating_change)
    user_rating = rating.get_user_rating(user_id)
    await message.answer(f"Работнику {state.get_data()['full_name']}, доверяют: {user_rating} раз!")
    await state.finish()


# Воркер
conn = sqlite3.connect('work.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY, name TEXT, work_count INTEGER, last_used INTEGER)''')
conn.commit()


@dp.message_handler(commands=['work'])
async def work(message: types.Message):
    user_id = message.from_user.id
    now = int(time.time())

    cursor.execute('SELECT last_used FROM users WHERE id=?', (user_id,))
    last_used = cursor.fetchone()

    if last_used and now - last_used[0] < 10800:
        remaining_time = timedelta(seconds=(10800 - (now - last_used[0])))
        remaining_time_str = str(remaining_time).split('.')[0]
        await message.reply(f"До следующей смены ещё:<b> {remaining_time_str} </b>.\n"
                            f"Попей пока чаю, порешай сканворды, или посмотри аниме <b>@reker_anime_bot</b>",
                            parse_mode=ParseMode.HTML)
        return

    cursor.execute('INSERT OR IGNORE INTO users (id, name, work_count, last_used) VALUES (?, ?, 0, ?)',
                   (user_id, message.from_user.full_name, now))
    cursor.execute('UPDATE users SET work_count=work_count+1, last_used=? WHERE id=?', (now, user_id))
    conn.commit()

    cursor.execute('SELECT work_count FROM users WHERE id=?', (user_id,))
    work_count = cursor.fetchone()[0]

    await message.reply(f"Ты отработал: {work_count} смен в этом коллективе!")


@dp.message_handler(commands=['top_work'])
async def work_stats(message: types.Message):
    cursor.execute('SELECT name, work_count FROM users ORDER BY work_count DESC')
    rows = cursor.fetchall()

    text = "Список самых отбитых работяг:\n"
    for i, row in enumerate(rows):
        text += "{}. {}: {} смен\n".format(i + 1, row[0], row[1])
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


# донат
@dp.message_handler(commands=['donate'])
async def startmes(message: types.Message):
    await message.answer('Поддержи <a href="https://projectkani.neyson.ru/">проект!</a>\n'
                         '<a href="https://www.donationalerts.com/r/neekrasoff">ДонатАлертс</a>',
                         parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['ad'])
async def ad(message: types.Message):
    await message.answer(AD_message, reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=AD_name, url=AD_url)]]))


@dp.message_handler(commands=['start'])
async def start(message: types.Message):
    await message.answer("Привет!\n"
                         "Это чат-бот для чата @factorychat_psk \nВведи /info - Если нужна подробная информация!\n"
                         "Есть вопросы? Напиши мне, и мы разберёмся!\n"
                         "@projectkani \n"
                         '<a href= "https://projectkani.neyson.ru">Made by ProjectKani community</a>',
                         parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['rplist'])
async def rplists(messgae: types.Message):
    await messgae.answer(
        f"Список РП-команд:\n{rplist}\n\nЕсли хотите больше рп команд, вы можете предложить свои варианты сюда: @projectkani",
        parse_mode=ParseMode.HTML)


@dp.message_handler(commands=['info'])
async def inform(message: types.Message):
    await message.answer("Бот умеет:\n"
                         "/mat_rus - Отправляет случайный мат на русском языке в чат с пояснением значения.\n"
                         "/mat_ukr - Отправляет случайный мат на украинском языке в чат с пояснением значения.\n"
                         "/work - Отработай свою смену во благо чата!!!\n"
                         "/echo_bot_on - Включает бота дразнилку.\n"
                         "/echo_bot_off - Выключает бота дразнилку.\n"
                         "/tea - Попей чаю в дружном коллективе!"
                         "/top_tea_drinkers - Самые преданные чаялюбы!"
                         "/top_work - Самые преданные работники!\n"
                         "/rating - Уровень доверия работнику. Определяеться кол-ом + или - на ваших сообщениях\n"
                         "Так же есть приведствие для новых пользователей.\n"
                         "РП-Команды на триггерах! Список слов: /rplist \n"
                         "/ad - Добровольно выложить рекламу. \n")


echo_bot_enabled = False


@dp.message_handler(commands='echo_bot_on')
async def cmd_echo_bot_on(message: types.Message):
    global echo_bot_enabled
    echo_bot_enabled = True
    await message.reply("Бот активен!")


@dp.message_handler(commands='echo_bot_off')
async def cmd_echo_bot_off(message: types.Message):
    global echo_bot_enabled
    echo_bot_enabled = False
    await message.reply("Бот отключён!")


@dp.message_handler(content_types=types.ContentType.TEXT)
async def echo_message(message: types.Message):
    global echo_bot_enabled
    if echo_bot_enabled:
        await message.reply(message.text)


# Чай бот
conn = sqlite3.connect('tea.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users
                (id INTEGER PRIMARY KEY, name TEXT, tea_count INTEGER, last_used INTEGER)''')
conn.commit()


@dp.message_handler(commands=['tea'])
async def tea_a(message: types.Message):
    user_id = message.from_user.id
    now = int(time.time())

    cursor.execute('SELECT last_used FROM users WHERE id=?', (user_id,))
    last_used = cursor.fetchone()

    if last_used and now - last_used[0] < 10:
        remaining_time = timedelta(seconds=(10 - (now - last_used[0])))
        remaining_time_str = str(remaining_time).split('.')[0]
        await message.reply(f"До следующего чаяпития ещё:<b> {remaining_time_str} </b>.\n"
                            f"Так что нужно идти работать, ну или порешай сканворды, или посмотри аниме <b>@reker_anime_bot</b>",
                            parse_mode=ParseMode.HTML)
        return

    cursor.execute('INSERT OR IGNORE INTO users (id, name, tea_count, last_used) VALUES (?, ?, 0, ?)',
                   (user_id, message.from_user.full_name, now))
    cursor.execute('UPDATE users SET tea_count=tea_count+1, last_used=? WHERE id=?', (now, user_id))
    conn.commit()

    cursor.execute('SELECT tea_count FROM users WHERE id=?', (user_id,))
    work_count = cursor.fetchone()[0]

    await message.reply(f"Ты выпил: {work_count} кружек чая!")


@dp.message_handler(commands=['top_tea_drinkers'])
async def work_stats(message: types.Message):
    cursor.execute('SELECT name, tea_count FROM users ORDER BY tea_count DESC')
    rows = cursor.fetchall()

    text = "Список чаяманов: \n"
    for i, row in enumerate(rows):
        text += "{}. {}: {} кружек\n".format(i + 1, row[0], row[1])
    await message.reply(text, parse_mode=ParseMode.MARKDOWN)


# 8ball бот
@dp.message_handler(commands=['8ball'])
async def eithball_handler(message: types.Message):
    # Открываем файл и читаем строки
    with open(ball, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    random_line = random.choice(lines)
    await message.reply(f"{random_line} \n"
                        f"{AD_message}", reply_markup=InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text=AD_name, url=AD_url)]]), parse_mode=ParseMode.HTML)


executor.start_polling(dp, skip_updates=True)