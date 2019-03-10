import sys
sys.path.append("application")

from flask import Flask, render_template
from application import app

server = Flask(__name__)

@server.route('/')
def index(update=False):
    cached = False if update else app.is_cache_updated()
    movies = app.get_movies(cached=cached)
    return render_template('index.html', movies=movies)

@server.route('/update')
def update():
    return index(update=True)