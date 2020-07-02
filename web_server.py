import bottle
import yaml

tokens_file = open('yt_download_tokens.yml', 'r', encoding="UTF-8")
tokens_data = yaml.safe_load(tokens_file)
tokens_file.close()


@bottle.get('/msg')
def send_youtube_download_link():
    token = bottle.request.query.t
    return f"LINK: {tokens_data[token]}"


bottle.run(host='localhost', port=8080, debug=True)
