from flask import Flask
import app

server = Flask(__name__)

@server.route('/')
def main():
    movies = app.get_movies(skip_cinema=True)
    return "Empty"

@server.route('/hello/<name>')
def hello_world(name):
    return 'Hello, {}!'.format(name)