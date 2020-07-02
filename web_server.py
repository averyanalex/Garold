#!/usr/bin/python3
# -*- coding: utf-8 -*-
import bottle
import pymysql
import yaml

debug = False

# импорт настроек
with open('config.yml', 'r', encoding="UTF=8") as settings_file:
    settings = yaml.safe_load(settings_file)
    settings_file.close()

mysql_connection = pymysql.connect(host=settings['db']['host'], user=settings['db']['user'], autocommit=True,
                                   password=settings['db']['password'], database=settings['db']['name'])
cursor = mysql_connection.cursor()
cursor.execute("SELECT VERSION()")
version = (cursor.fetchone())[0]
print(f"Пул подключений к БД {settings['db']['name']} на {version} создан")


@bottle.get('/redirect')
def send_youtube_download_link():
    token = bottle.request.query.token
    cursor.execute(f"SELECT `url` FROM `redirects` WHERE `token` = %s", (token,))
    url_row = cursor.fetchone()
    if url_row is not None:
        return bottle.redirect(url=url_row[0], code=301)
    else:
        return "Неверный токен"


bottle.run(host='0.0.0.0', port=48000, debug=True)
