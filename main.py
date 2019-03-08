# from flask import Flask
# app = Flask(__name__)


# @app.route('/')
# def main():
#     return "Empty"

# @app.route('/hello/<name>')
# def hello_world(name):
#     return 'Hello, {}!'.format(name)


##############################################

from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from hashlib import md5
import json
import re
import asyncio
import concurrent.futures
import datetime
import sys

try:
    with open('omdb_api_key', 'r') as file:
        OMDB_API_KEY = file.read()
except:
    print("No OMDB API key found!")
    sys.exit(1)

FILMWEB_POSTER_URL = "http://1.fwcdn.pl/po"

FWEB_API_ENG_TITLE_IDX = 1
FWEB_API_RATING_IDX = 2
FWEB_API_YEAR_IDX = 5
FWEB_API_FORUM_URL_IDX = 8
FWEB_API_POSTER_IDX = 11

MAX_WORKERS = 20
FILTER_KEYWORDS = ["National Theatre Live", "LIGA MISTRZÓW", "Balet Bolszoj", "Met Opera"]

def to_float(value, decimals=1):
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        return round(float(value), decimals)
    except:
        return 0.0

class Rating:
    def __init__(self, mul=0.0, fweb=0.0, imdb=0.0):
        self.mul = mul
        self.fweb = fweb
        self.imdb = imdb

    @property
    def mul(self):
        return self._mul
    
    @property
    def fweb(self):
        return self._fweb

    @property
    def imdb(self):
        return self._imdb

    @mul.setter
    def mul(self, value):
        self._mul = to_float(value)

    @fweb.setter
    def fweb(self, value):
        self._fweb = to_float(value)

    @imdb.setter
    def imdb(self, value):
        self._imdb = to_float(value)

        
class Movie:
    def __init__(self, title="", votes="", date="", description="", genres="", released=False):
        self.title = title
        self.title_eng = ""
        self.votes = votes
        self.date = date
        self.description = description
        self.genres = genres
        self.year = 0
        self.rating = Rating()
        self.url = None
        self.poster_imdb = None
        self.poster_fweb = None
        self.released = released

    def __repr__(self):
        return "{}: {}".format(self.title, self.get_rating())

    def __lt__(self, other):
        return self.get_rating() < other.get_rating()

    def get_rating(self):
        """ Returns movie rating.
        Movies will be compared with each other according to this value.
        """ 
        return self.rating.imdb

    def get_poster(self):
        return self.poster_imdb or self.poster_fweb

def sortMoviesDescending(movies):
    """ Sort movies by rating in descending order
    """
    return sorted(movies, reverse=True)

def get_filmweb_movie_id(title):
    url = 'http://www.filmweb.pl/search/live?q=' + title.replace(' ', '%20');
    html = str(requests.get(url).text);
    return html.split('\\c')[1];

def get_filmweb_signature(idd):
    method = f'getFilmInfoFull [{idd}]'
    return md5(method.encode('utf-8') + b"\\n" + b"android" + b"qjcGhW2JnvGT9dfCt3uT_jozR3s").hexdigest()

def get_filmweb_api_data(title):
    idd = get_filmweb_movie_id(title)
    sig = get_filmweb_signature(idd)
    url = f'https://ssl.filmweb.pl/api?version=1.0&appId=android&methods=getFilmInfoFull%20[{idd}]%5Cn&signature=1.0,{sig}'
    html = requests.get(url).text;
    data = re.sub(r" t:\d+", "", html.split('\n')[1])
    return (title, json.loads(data))

async def get_all_filmweb_api_data(movies):
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, get_filmweb_api_data, title) for title in movies.keys()]
        for title, data in await asyncio.gather(*futures):
            movies[title].rating.fweb = data[FWEB_API_RATING_IDX]
            movies[title].title_eng = data[FWEB_API_ENG_TITLE_IDX]
            movies[title].year = data[FWEB_API_YEAR_IDX]
            poster = data[FWEB_API_POSTER_IDX]
            if poster:
                movies[title].poster_fweb = FILMWEB_POSTER_URL + poster
            url = data[FWEB_API_FORUM_URL_IDX]
            if url:
                trim = '/discussion'
                if url.endswith(trim):
                    url = url[:-len(trim)]
            movies[title].url = url

def get_omdb_url(title, year):
    url = "http://www.omdbapi.com/?t="
    url += title.replace(" ", "+")
    # url += "&y=" + str(year) # this is probably negligible
    url += "&apikey=" + OMDB_API_KEY  
    return url

def get_omdb_api_data(movie):
    # if we reached here at least one title exists so this is safe
    for title in [movie.title_eng, movie.title]:
        if title:
            url = get_omdb_url(title, movie.year)
            raw = requests.get(url).text
            data = json.loads(raw)
            if data["Response"] == "True":
                break

    return (movie.title, data)

async def get_all_omdb_api_data(movies):
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, get_omdb_api_data, movie) for movie in movies.values()]
        for title, data in await asyncio.gather(*futures):
            if data["Response"] == "True":
                movies[title].rating.imdb = data["imdbRating"]
                movies[title].runtime = data["Runtime"]
                movies[title].poster_imdb = data["Poster"]
            else:
                print("no data for: {}".format(title))

MULTIKINO_URL = "https://multikino.pl/repertuar/gdansk"

SKIP_CINEMA = True

options = Options()
options.add_argument('--disable-gpu')
options.add_argument('--no-sandbox')
options.add_argument('--headless')
# options.set_headless(headless=True)

if SKIP_CINEMA:
    with open('html.txt', 'r', encoding='utf-8') as file:
        html = file.read()
else:
    browser = webdriver.Chrome(options=options)
    browser.get(MULTIKINO_URL)
    html = browser.page_source
    browser.quit()
    with open('html.txt', 'w', encoding='utf-8') as file:
        file.write(html)


movies = []

soup = BeautifulSoup(html, "html.parser")
for movie in soup.find_all(class_='filmlist__info--inverted'):
    title = movie.find(attrs={"rv-text": "item.title"}).getText()
    rating = movie.find(attrs={"rv-text": "item.rank_value"}).getText()
    votes = movie.find(attrs={"rv-text": "item.rank_votes"}).getText()
    date = movie.find(attrs={"rv-text": "item.info_release"}).getText()
    description = movie.find(attrs={"rv-text": "item.synopsis_short"}).getText()
    genres = list(map(lambda item: item.getText(), movie.find_all(attrs={"rv-text": "genre.name"}))) or \
        list(map(lambda item: item.getText(), movie.find_all(attrs={"rv-text": "category.name"})))
    genres = ', '.join(genres)

    d1 = datetime.datetime.strptime(date, "%d.%m.%Y")
    if d1 > datetime.datetime.now() + datetime.timedelta(days=7):
        continue

    if any(keyword in title for keyword in FILTER_KEYWORDS):
        continue

    released = d1 <= datetime.datetime.now()

    movie = Movie(title=title, votes=votes, date=date, description=description, genres=genres, released=released)
    movie.rating.mul = rating
    movies.append(movie)

hash_movies = {movie.title: movie for movie in movies}

print('Total movies found (+7 days from now): {}'.format(len(movies)))

loop = asyncio.get_event_loop()
loop.run_until_complete(get_all_filmweb_api_data(hash_movies))
loop.run_until_complete(get_all_omdb_api_data(hash_movies))

movies = sortMoviesDescending(movies)

print()
print()
for movie in movies:
    print(movie.title, movie.title_eng, movie.rating.imdb, movie.rating.fweb, movie.date, movie.get_poster())





# classic for loop url processing: [Finished in 171.7s]
# each movie as separate parallel request: [Finished in 5.9s]


# for movie in movies:
#     title = movie.title
#     data = get_movie_data(title)
#     print(title, data)


# import threading
# threads = [threading.Thread(target=get_movie_data, args=(movie.title,)) for movie in movies] 
# for thread in threads:
#     thread.start()
# for thread in threads:
#     thread.join()


























# from flask import Flask
# app = Flask(__name__)


# @app.route('/')
# def main():
#     zup = BeautifulSoup(html, 'html.parser')
#     titles = []
#     for movie in zup.find_all(class_='filmlist__info--inverted'):
#         title = movie.find(attrs={"rv-text": "item.title"}).getText()
#         titles.append(title)

#     return '<br>'.join(titles)

# @app.route('/hello/<name>')
# def hello_world(name):
#     return 'Hello, {}!'.format(name)