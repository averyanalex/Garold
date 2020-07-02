#!/usr/bin/python3
# -*- coding: utf-8 -*-
import bottle

tokens_data = {'help': 12345678}


@bottle.get('/msg')
def send_youtube_download_link():
    token = bottle.request.query.t
    return f"LINK: {tokens_data[token]}"


bottle.run(host='0.0.0.0', port=48000, debug=False)
