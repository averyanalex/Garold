#!/usr/bin/python3
# -*- coding: utf-8 -*-

##################################
#        ИМПОРТ БИБЛИОТЕК        #
##################################
print("Начат импорт библиотек")
import asyncio
import logging
import queue
import random
import subprocess
import threading
import uuid
import pymysql
import aiomysql
import discord
import yaml
import youtube_dl
import sys
from Cybernator import Paginator
from discord.ext import commands

try:
    import uvloop
    print("Отлично! Будем использовать uvloop")
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except ModuleNotFoundError:
    print("У вас не установлен uvloop")

debug = False

# импорт языков
with open('lang.yml', 'r', encoding="UTF-8") as lang_file:
    lang_data = yaml.safe_load(lang_file)
    lang_file.close()
# импорт данных
with open('data.yml', 'r', encoding="UTF-8") as data_file:
    data = yaml.safe_load(data_file)
    data_file.close()
# импорт настроек
with open('config.yml', 'r', encoding="UTF-8") as settings_file:
    config = yaml.safe_load(settings_file)
    settings_file.close()

# включаем логи в зависимости от настроек
discord_logger = logging.getLogger('discord')
aiomysql_logger = logging.getLogger('aiomysql')

if debug:
    discord_logger.setLevel(logging.INFO)
    aiomysql_logger.setLevel(logging.INFO)
else:
    discord_logger.setLevel(logging.ERROR)
    aiomysql_logger.setLevel(logging.ERROR)

discord_log_handler = logging.FileHandler(filename='logs/discord.log', encoding='utf-8', mode='w')
discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
discord_logger.addHandler(discord_log_handler)

aiomysql_log_handler = logging.FileHandler(filename='logs/aiomysql.log', encoding='utf-8', mode='w')
aiomysql_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
aiomysql_logger.addHandler(aiomysql_log_handler)

##################################
#           НАСТРОЙКИ            #
##################################

default_lang = "ru"
default_prefix = "&"

##################################
#           БАЗА ДАННЫХ          #
##################################
loop = asyncio.get_event_loop()


# подключаемся к БД
async def mysql_connect():
    try:
        if debug:
            created_pool = await aiomysql.create_pool(host=config['db']['host'], user=config['db']['user'],
                                                      password=config['db']['password'],
                                                      db=config['db']['name'], charset=config['db']['charset'],
                                                      autocommit=True, loop=loop, maxsize=100,
                                                      minsize=5, echo=True)
        else:
            created_pool = await aiomysql.create_pool(host=config['db']['host'], user=config['db']['user'],
                                                      password=config['db']['password'],
                                                      db=config['db']['name'], charset=config['db']['charset'],
                                                      autocommit=True, loop=loop, maxsize=100,
                                                      minsize=5, echo=False)
    except pymysql.err.OperationalError:
        print(f"Не могу подключиться к MySQL серверу на {config['db']['host']}, проверьте соединение с интернетом!")
        sys.exit(16)
    con = await created_pool.acquire()
    cursor = await con.cursor()
    await cursor.execute("SELECT VERSION()")
    version = (await cursor.fetchone())[0]
    print(f"Пул подключений к БД {config['db']['name']} на {version} создан")
    await created_pool.release(con)
    return created_pool


print("Начинаю подключение к БД")
pool = loop.run_until_complete(mysql_connect())


async def get_prefix(context):
    con = await pool.acquire()
    cur = await con.cursor()
    if context.guild is not None:
        await cur.execute(f"SELECT `prefix` FROM `guilds` WHERE `id` = %s", (context.guild.id,))
        prefix_row = await cur.fetchone()
        if prefix_row is not None:
            await pool.release(con)
            return prefix_row[0]
        else:
            await cur.execute(f"INSERT INTO `guilds` (`id`, `lang`, `prefix`) VALUES (%s, %s, %s)",
                              (context.guild.id, default_lang, default_prefix))
            print(f"В БД был добавлен сервер №{context.guild.id}")
            await pool.release(con)
            return default_prefix
    else:
        return "&"


async def get_message_prefix(given_bot, message):
    con = await pool.acquire()
    cur = await con.cursor()
    if message.guild is not None:
        await cur.execute(f"SELECT `prefix` FROM `guilds` WHERE `id` = %s", (message.guild.id,))
        prefix_row = await cur.fetchone()
        if prefix_row is not None:
            await pool.release(con)
            return prefix_row[0]
        else:
            await cur.execute(f"INSERT INTO `guilds` (`id`, `lang`, `prefix`) VALUES (%s, %s, %s)",
                              (message.guild.id, default_lang, default_prefix))
            print(f"В БД был добавлен сервер №{message.guild.id}")
            await pool.release(con)
            return default_prefix
    else:
        return default_prefix


# создаём бота
bot = commands.Bot(command_prefix=get_message_prefix, case_insensitive=True)


##################################
#            ФУНКЦИИ             #
##################################

# получение языка
async def get_lang(context):
    con = await pool.acquire()
    cur = await con.cursor()
    if context.guild is not None:
        await cur.execute(f"SELECT `lang` FROM `guilds` WHERE `id` = %s", (context.guild.id,))
        guild_lang = (await cur.fetchone())[0]
        await pool.release(con)
        return guild_lang
    else:
        await cur.execute(f"SELECT `lang` FROM `users` WHERE `id` = %s", (context.author.id,))
        lang_row = await cur.fetchone()
        if lang_row is not None:
            await pool.release(con)
            return lang_row[0]
        else:
            await cur.execute("INSERT INTO `users` (`id`, `lang`) VALUES (%s, %s)",
                              (context.author.id, default_lang))
            await pool.release(con)
            return default_lang


def read_kbd_input(input_queue):
    print("Готов к обработке ввода с клавиатуры")
    while True:
        input_str = input()
        input_queue.put(input_str)


##################################
#    АСИНХРОННЫЕ СОБЫТИЯ БОТА    #
##################################

# бот подключен
@bot.event
async def on_connect():
    print("Подключен к серверам Discord")


# соеденение потеряно
@bot.event
async def on_disconnect():
    print("Соеденение с Discord потеряно!")


# бот запущен
@bot.event
async def on_ready():
    guilds = await bot.fetch_guilds(limit=None).flatten()
    await bot.change_presence(activity=discord.Game(name=f"I am on {len(guilds)} servers"))
    print(f"Бот успешно запущен, количество серверов: {len(guilds)}")


# бота добавили на сервер
@bot.event
async def on_guild_join(guild):
    # добавляем сервер в БД
    con = await pool.acquire()
    cur = await con.cursor()
    await cur.execute("SELECT `prefix` FROM `guilds` WHERE `id` = %s", (guild.id,))
    guilds = await bot.fetch_guilds(limit=None).flatten()
    await bot.change_presence(activity=discord.Game(name=f"I am on {len(guilds)} servers"))
    if len(await cur.fetchall()) == 0:
        await cur.execute(f"INSERT INTO `guilds` (`id`, `lang`, `prefix`) VALUES (%s, %s, %s)",
                          (guild.id, default_lang, default_prefix))
        print(f"В БД был добавлен сервер №{guild.id}")
    else:
        print(f"Меня вернули на сервер №{guild.id}")
    await pool.release(con)


# ошибка выполения команды
@bot.event
async def on_command_error(ctx, error):
    emoji_guild = await bot.fetch_guild(719833247374377030)
    emoji_load = discord.utils.get(emoji_guild.emojis, name="load")
    await ctx.message.add_reaction(str(emoji_load))
    errors_channel = bot.get_channel(720535391001772143)
    if ctx.guild is not None:
        await errors_channel.send(embed=discord.Embed(description=f"{ctx.author} на сервере {ctx.guild.name} "
                                                                  f"спровоцировал ошибку: {error}",
                                                      colour=discord.Color.red()))
    else:
        await errors_channel.send(embed=discord.Embed(description=f"{ctx.author}, написав в ЛС боту, "
                                                                  f"спровоцировал ошибку: {error}",
                                                      colour=discord.Color.red()))


@bot.event
async def on_message(message):
    await bot.process_commands(message)


##################################
#            КОМАНДЫ             #
##################################


@bot.command()
async def ping(ctx):
    await ctx.send(bot.latency)


@bot.command()
async def send(ctx, member: discord.Member, *, message):
    guild_lang = await get_lang(ctx)
    await member.send(f"{ctx.author} {lang_data[guild_lang]['send']}: {message}")


# создаём свою команду help
bot.remove_command("help")


# команда помощи
@bot.command()
async def help(ctx):
    # узнаём язык
    guild_lang = await get_lang(ctx)
    # узнаём префикс
    guild_prefix = await get_prefix(ctx)
    embeds = []
    # выставляем страницы
    for i in range(0, len(lang_data[guild_lang]['help']['pages'])):
        page_title = lang_data[guild_lang]['help']['title']
        page_title = page_title.replace("%current_page%", str(i + 1))
        page_title = page_title.replace("%total_pages%", str(len(lang_data[guild_lang]['help']['pages'])))
        embed_description = lang_data[guild_lang]['help']['pages'][i]
        embed_description = embed_description.replace("%cp%", guild_prefix)
        embeds.append(discord.Embed(title=page_title, description=embed_description, color=discord.Color.green()))
    # создаём массив страниц
    msg = await ctx.send(embed=embeds[0])
    page = Paginator(bot, msg, only=ctx.author, use_more=False, embeds=embeds, footer=False, timeout=120)
    await page.start()


# тестовая команда
@bot.command()
async def test(ctx, *, arg):
    await ctx.send(arg)


# команда спама
@commands.has_permissions(administrator=True)
@bot.command()
async def spam(ctx, arg):
    for i in range(0, int(arg)):
        await ctx.send(f'Ну вот я спамлю уже {i + 1} раз')


# команда для смена префикса
@bot.command(no_pm=True)
@commands.has_permissions(administrator=True)
async def prefix(ctx, new_prefix=None):
    current_prefix = await get_prefix(ctx)
    if new_prefix is None:  # пользователь не указал новый префикс
        message_to_send = lang_data[await get_lang(ctx)]['prefix']['current']
        message_to_send = message_to_send.replace('%current_prefix%', current_prefix)
        await ctx.send(message_to_send)
    else:
        # меняем префикс на новый
        # подключаемся к БД
        con = await pool.acquire()
        cur = await con.cursor()
        message_to_send = lang_data[await get_lang(ctx)]['prefix']['changed']
        message_to_send = message_to_send.replace('%current_prefix%', current_prefix)
        message_to_send = message_to_send.replace('%new_prefix%', new_prefix)
        await cur.execute("UPDATE `guilds` SET `prefix` = %s WHERE `id` = %s", (new_prefix, ctx.guild.id))
        await ctx.send(message_to_send)
        await pool.release(con)


# команда смена языка
@bot.command(no_pm=True)
@commands.has_permissions(administrator=True)
async def lang(ctx):
    await ctx.send("started")

    def check_reaction(react):
        return react.message_id == ctx.message.id and react.member.id == ctx.author.id

    payload = await bot.wait_for('raw_reaction_add', timeout=60, check=check_reaction)
    await ctx.send(payload.emoji.name)


# приглашение на сервер поддержки
@bot.command()
async def support(ctx):
    await ctx.send("https://discord.gg/kRh5s9f")


# отправляет ссылку на добавления бота на сервер
@bot.command()
async def invite(ctx):
    guild_lang = await get_lang(ctx)
    await ctx.send(embed=discord.Embed(description=f"{lang_data[guild_lang]['invite']}\nhttps://discord.com/oauth2"
                                                   f"/authorize?client_id"
                                                   f"=719498715769077771&permissions=8&scope=bot",
                                       colour=discord.Color.blue()))


# тестовая команда, выводит всех участников всех серверов
@bot.command()
async def members(ctx):
    async with ctx.typing():
        for guild in bot.guilds:
            for member in guild.members:
                await ctx.send(member)


@bot.command(name="meme", aliases=("mem", "мем", "прикол", "пикча"))
async def meme(ctx):
    async with ctx.typing():
        random_meme = random.choice(data['memes']['ru'])
        embed_with_meme = discord.Embed(color=discord.Color.blue())
        embed_with_meme.set_image(url=random_meme)
    await ctx.send(embed=embed_with_meme)


@bot.command()
async def download(ctx, link_to_download):
    con = await pool.acquire()
    cur = await con.cursor()
    options = {  # настройки youtube_dl
        'outtmpl': '%(title)s-%(id)s.%(ext)s',
        'format': 'best',
        'silent': True
    }
    async with ctx.typing():
        ydl = youtube_dl.YoutubeDL(options)
        r = ydl.extract_info(link_to_download, download=False)  # Вставляем нашу ссылку с ютуба
        video_url = r['url']  # Получаем прямую ссылку на скачивание видео
        redirect_id = (str(uuid.uuid4()))[0:8]
        await cur.execute(f"INSERT INTO `redirects` (`token`, `url`) VALUES (%s, %s)",
                          (redirect_id, video_url))
        url_to_send = f"https://garold.forumidey.ru/redirect?token={redirect_id}"
        await ctx.send(embed=discord.Embed(title=lang_data[(await get_lang(ctx))]['download']['download_now'],
                                           url=url_to_send))
    await pool.release(con)


# @bot.command(pass_context=True, no_pm=True)
# async def play(ctx, *, song: str):
#     voice_channel = ctx.author.voice.channel
#     # only play music if user is in a voice channel
#     if voice_channel is not None:
#         # grab user's voice channel
#         channel = voice_channel.name
#         await ctx.send('User is in channel: ' + channel)
#         # create StreamPlayer
#         vc = await voice_channel.connect()
#         vc.play(discord.FFmpegPCMAudio('testing.mp3'), after=lambda e: print('done', e))
#         vc.resume()
#         await asyncio.sleep(10)
#         await ctx.send(vc.is_playing())


##################################
#   РЕГУЛЯРНЫЕ ФОНОВЫЕ ЗАДАЧИ    #
##################################


# блокировщик запуска других экземпляров бот
async def locker():
    con = await pool.acquire()
    cur = await con.cursor()
    while True:
        await cur.execute("UPDATE `dblock` SET `time` = UTC_TIMESTAMP() WHERE `id` = '1'")
        await asyncio.sleep(1)


# переодически закрываем ненужные подключения к БД
async def pool_cleaner():
    await asyncio.sleep(180)
    await pool.clear()


# обработчик команд с клавиатуры
async def keyboard_handler():
    input_queue = queue.Queue()

    input_thread = threading.Thread(target=read_kbd_input, args=(input_queue,), daemon=True)
    input_thread.start()

    while True:
        if input_queue.qsize() > 0:
            input_str = input_queue.get()
            print(f"Вы ввели: {input_str}")

        await asyncio.sleep(0.5)


##################################
#            ЗАПУСК              #
##################################


# запускаем фоновые задачи
bot.loop.create_task(locker())
bot.loop.create_task(pool_cleaner())
bot.loop.create_task(keyboard_handler())

# запускаем веб сервер
with open('logs/web.log', 'w', encoding="UTF-8") as web_log_file:
    print("Запуск веб-сервера")
    web_server_process = subprocess.Popen(['python', 'web_server.py'], stdout=web_log_file,
                                          stderr=web_log_file, stdin=subprocess.DEVNULL)

bot.run(config['token'])
