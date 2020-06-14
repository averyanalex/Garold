#!/usr/bin/python3
# -*- coding: utf-8 -*-


##################################
#        ИМПОРТ БИБЛИОТЕК        #
##################################
import discord
import aiomysql
import yaml
from Cybernator import Paginator
from discord.ext import commands
import asyncio
import logging

debug = False

# импорт языков
lang_file = open('lang.yml', 'r', encoding="UTF-8")
lang_data = yaml.safe_load(lang_file)
lang_file.close()
# импорт данных
data_file = open('data.yml', 'r', encoding="UTF=8")
data = yaml.safe_load(data_file)
data_file.close()
# импорт настроек
settings_file = open('config.yml', 'r', encoding="UTF=8")
settings = yaml.safe_load(settings_file)
settings_file.close()
# включаем логи в зависимости от настроек
if debug:
    # discord
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.INFO)
    discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    discord_logger.addHandler(discord_log_handler)
    # aiomysql
    aiomysql_logger = logging.getLogger('aiomysql')
    aiomysql_logger.setLevel(logging.INFO)
    aiomysql_log_handler = logging.FileHandler(filename='aiomysql.log', encoding='utf-8', mode='w')
    aiomysql_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    aiomysql_logger.addHandler(aiomysql_log_handler)
else:
    # discord
    discord_logger = logging.getLogger('discord')
    discord_logger.setLevel(logging.ERROR)
    discord_log_handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
    discord_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    discord_logger.addHandler(discord_log_handler)
    # aiomysql
    aiomysql_logger = logging.getLogger('aiomysql')
    aiomysql_logger.setLevel(logging.ERROR)
    aiomysql_log_handler = logging.FileHandler(filename='aiomysql.log', encoding='utf-8', mode='w')
    aiomysql_log_handler.setFormatter(logging.Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
    aiomysql_logger.addHandler(aiomysql_log_handler)


##################################
#           НАСТРОЙКИ            #
##################################

default_lang = "en"
default_prefix = "#"

##################################
#           БАЗА ДАННЫХ          #
##################################
loop = asyncio.get_event_loop()


# подключаемся к БД
async def mysql_connect():
    if debug:
        created_pool = await aiomysql.create_pool(host=settings['db']['host'], user=settings['db']['user'],
                                                  password=settings['db']['password'],
                                                  db=settings['db']['name'], charset=settings['db']['charset'],
                                                  autocommit=True, loop=loop, maxsize=100,
                                                  minsize=5, echo=True)
    else:
        created_pool = await aiomysql.create_pool(host=settings['db']['host'], user=settings['db']['user'],
                                                  password=settings['db']['password'],
                                                  db=settings['db']['name'], charset=settings['db']['charset'],
                                                  autocommit=True, loop=loop, maxsize=100,
                                                  minsize=5, echo=False)
    con = await created_pool.acquire()
    cursor = await con.cursor()
    await cursor.execute("SELECT VERSION()")
    version = (await cursor.fetchone())[0]
    print(f"Пул подключений к БД {settings['db']['name']} на {version} создан")
    await created_pool.release(con)
    return created_pool


print("Начинаю подключение к БД")
pool = loop.run_until_complete(mysql_connect())


async def get_prefix(guild_id):
    con = await pool.acquire()
    cur = await con.cursor()
    await cur.execute(f"SELECT `prefix` FROM `guilds` WHERE `id` = %s", (guild_id,))
    prefix_row = await cur.fetchone()
    if prefix_row is not None:
        await pool.release(con)
        return prefix_row[0]
    else:
        await cur.execute(f"INSERT INTO `guilds` (`id`, `lang`, `prefix`) VALUES (%s, %s, %s)",
                          (guild_id, default_lang, default_prefix))
        print(f"В БД был добавлен сервер №{guild_id}")
        await pool.release(con)
        return default_prefix


async def get_message_prefix(bot_but_what_is_it, message):
    return get_prefix(message.guild.id)


# создаём бота
bot = commands.Bot(command_prefix=get_message_prefix)


##################################
#            ФУНКЦИИ             #
##################################

# получение префикса
async def get_lang(guild_id):
    con = await pool.acquire()
    cur = await con.cursor()
    await cur.execute(f"SELECT `lang` FROM `guilds` WHERE `id` = %s", (guild_id,))
    guild_lang = (await cur.fetchone())[0]
    await pool.release(con)
    return guild_lang


##################################
#    АСИНХРОННЫЕ СОБЫТИЯ БОТА    #
##################################

# бот запущен
@bot.event
async def on_ready():
    guilds = await bot.fetch_guilds(limit=None).flatten()
    await bot.change_presence(activity=discord.Game(name=f"I am on {len(guilds)} servers"))
    print(f"Бот запущен, количество серверов: {len(guilds)}")


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
    await errors_channel.send(embed=discord.Embed(description=f"{ctx.author} на сервере {ctx.guild.name} спровоцировал "
                                                              f"ошибку: {error}", colour=discord.Color.red()))


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
    guild_lang = await get_lang(ctx.guild.id)
    await member.send(f"{ctx.author} {lang_data[guild_lang]['send']}: {message}")


# создаём свою команду help
bot.remove_command("help")


# команда помощи
@bot.command()
async def help(ctx):
    # узнаём язык
    guild_lang = await get_lang(ctx.guild.id)
    # узнаём префикс
    guild_prefix = await get_prefix(ctx.guild.id)
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
@bot.command()
@commands.has_permissions(administrator=True)
async def prefix(ctx, new_prefix=None):
    current_prefix = await get_prefix(ctx.guild.id)
    if new_prefix is None:  # пользователь не указал новый префикс
        message_to_send = lang_data[await get_lang(ctx.guild.id)]['prefix']['current']
        message_to_send = message_to_send.replace('%current_prefix%', current_prefix)
        await ctx.send(message_to_send)
    else:
        # меняем префикс на новый
        # подключаемся к БД
        con = await pool.acquire()
        cur = await con.cursor()
        message_to_send = lang_data[await get_lang(ctx.guild.id)]['prefix']['changed']
        message_to_send = message_to_send.replace('%current_prefix%', current_prefix)
        message_to_send = message_to_send.replace('%new_prefix%', new_prefix)
        await cur.execute("UPDATE `guilds` SET `prefix` = %s WHERE `id` = %s", (new_prefix, ctx.guild.id))
        await ctx.send(message_to_send)
        await pool.release(con)


# команда смена языка
# todo: переделать команду на выбор языка с помощью реакций
@bot.command()
@commands.has_permissions(administrator=True)
async def lang(ctx, given_lang):
    con = await pool.acquire()
    cur = await con.cursor()
    await cur.execute(f"UPDATE `guilds` SET `lang` = %s WHERE `id` = %s", (given_lang, ctx.guild.id))
    await ctx.send("Новый язык " + given_lang)
    await pool.release(con)


# приглашение на сервер поддержки
@bot.command()
async def support(ctx):
    await ctx.send("https://discord.gg/kRh5s9f")


# отправляет ссылку на добавления бота на сервер
@bot.command()
async def invite(ctx):
    guild_lang = await get_lang(ctx.guild.id)
    await ctx.send(embed=discord.Embed(description=f"{lang_data[guild_lang]['invite']}\nhttps://discord.com/oauth2"
                                                   f"/authorize?client_id"
                                                   f"=719498715769077771&permissions=8&scope=bot",
                                       colour=discord.Color.blue()))


# тестовая команда, выводит всех участников всех серверов
@bot.command()
async def members(ctx):
    for guild in bot.guilds:
        for member in guild.members:
            await ctx.send(member)


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


##################################
#            ЗАПУСК              #
##################################

# запускаем фоновые задачи
bot.loop.create_task(locker())
bot.loop.create_task(pool_cleaner())


bot.run(settings['token'])
