import sys
sys.path.append("application")

from flask import Flask, render_template
from application import app

server = Flask(__name__)

@server.route('/')
def index():
    movies = app.get_movies()
    return render_template('index.html', movies=movies)