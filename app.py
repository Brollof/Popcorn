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
from imdb import IMDb
from movie import Movie

MULTIKINO_URL = "https://multikino.pl/repertuar/gdansk"
FILMWEB_POSTER_URL = "http://1.fwcdn.pl/po"

FWEB_API_ENG_TITLE_IDX = 1
FWEB_API_RATING_IDX = 2
FWEB_API_YEAR_IDX = 5
FWEB_API_FORUM_URL_IDX = 8
FWEB_API_POSTER_IDX = 11

FILTER_KEYWORDS = ["National Theatre Live", "LIGA MISTRZÓW", "Balet Bolszoj", "Met Opera"]

imdb = IMDb()

def sortMoviesDescending(movies):
    """ Sort movies by rating in descending order.
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

def get_imdb_data(movie):
    result = imdb.search_movie(movie.title)
    if result:
        data = result[0]
        imdb.update(data)
    else:
        data = None

    return (movie.title, data)

async def get_all_imdb_api_data(movies):
    with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
        loop = asyncio.get_event_loop()
        futures = [loop.run_in_executor(executor, get_imdb_data, movie) for movie in movies.values()]
        for title, data in await asyncio.gather(*futures):
            if data:
                movies[title].rating.imdb = data.get('rating', 0)
                movies[title].poster_imdb = data.get('cover url', None)
                movies[title].runtime = data.get('runtime', 0)
                # movies[title].poster_full = data['full-size cover url']
            else:
                print(f"no data for: {movies[title].title}")

def get_movies(skip_cinema=False):
    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    # options.set_headless(headless=True)

    if skip_cinema:
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


    loop = asyncio.new_event_loop()
    loop.run_until_complete(get_all_filmweb_api_data(hash_movies))
    loop.run_until_complete(get_all_imdb_api_data(hash_movies))

    return sortMoviesDescending(movies)


if __name__ == '__main__':
    movies = get_movies(skip_cinema=True)
    print()
    for movie in movies:
        print(movie.title, movie.title_eng, (movie.rating.imdb, movie.rating.fweb), movie.get_poster(), movie.runtime)