from bs4 import BeautifulSoup
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from hashlib import md5
import json
import re
import asyncio
import concurrent.futures
from datetime import datetime, timedelta
from imdb import IMDb
from movie import Movie
from utils import save_cache, load_cache, get_mod_time
import os

# Full link example: "https://multikino.pl/repertuar/gdansk/teraz-gramy/alfabetyczny?data=02-05-2019,08-05-2019"
MULTIKINO_URL = "https://multikino.pl/repertuar/gdansk/teraz-gramy/alfabetyczny"
FILMWEB_POSTER_URL = "http://1.fwcdn.pl/po"

FWEB_API_ENG_TITLE_IDX = 1
FWEB_API_RATING_IDX = 2
FWEB_API_YEAR_IDX = 5
FWEB_API_FORUM_URL_IDX = 8
FWEB_API_POSTER_IDX = 11

FILTER_KEYWORDS = ["National Theatre Live", "LIGA MISTRZÓW", "Balet Bolszoj", "Met Opera"]
MOVIES_CACHE = os.path.join(os.path.dirname(__file__), 'movies.data')

imdb = IMDb()

def save_to_file(filename, data):
    try:
        with open(filename, "w") as file:
            file.write(data)
        print(f"Data saved to file: {filename}")
    except Exception as ex:
        print(f"Writing to file {filename} failed!")
        print(ex)

def create_multikino_url():
    start = datetime.now()
    end = start + timedelta(days=6)
    date_range = f"?data={start.day:02}-{start.month:02}-{start.year},{end.day:02}-{end.month:02}-{end.year}"
    return MULTIKINO_URL + date_range

def sort_movies_descending(movies):
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
                movies[title].poster_imdb_full = data.get('full-size cover url', None)
                movies[title].runtime = data.get('runtime', [0])[0]
            else:
                print(f"no data for: {movies[title].title}")

def is_cache_updated():
    mod_time = get_mod_time(MOVIES_CACHE)
    mod_time = datetime.fromtimestamp(mod_time)
    delta = datetime.now() - mod_time
    return delta.total_seconds() // 3600 < 24

def get_movies(cached=False):
    if cached:
        print("Returning cached data")
        return load_cache(MOVIES_CACHE)

    options = Options()
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--headless')
    chrome_bin_path = os.environ.get('GOOGLE_CHROME_BIN', None)
    chromedriver_path = os.environ.get('CHROMEDRIVER_PATH', None)
    if not chrome_bin_path or not chromedriver_path:
        print('Chrome problem. Check if chrome and chromedriver are installed and envionmental variables are set.')
        return []

    options.binary_location = chrome_bin_path
    # options.set_headless(headless=True)

    url = create_multikino_url()
    print(f"Getting {url} ...")
    browser = webdriver.Chrome(executable_path=chromedriver_path, options=options)
    browser.get(url)
    html = browser.page_source
    save_to_file("multikino.html", html)
    print(f"browser: {browser}")
    browser.quit()

    movies = []

    print("Parsing...")
    soup = BeautifulSoup(html, "html.parser")
    for movie in soup.find_all(class_='filmlist__info'):
        title = movie.select(".filmlist__title > span")[0].get_text()
        try:
            rating = movie.find(attrs={"rv-show": "film.rank_value"}).select("span")[0].get_text()
            votes = movie.find(attrs={"rv-show": "film.rank_votes"}).select("span")[0].get_text()
        except AttributeError:
            print(f"No rating for {title}")
        except Exception as e:
            print(f"Something really bad happend: {e}")

        description = movie.select(".filmlist__synopsis > p")[0].get_text()
        genres = list(map(lambda item: item.get_text(), movie.find_all("a", class_="film-details__item")))
        genres = ', '.join(genres) or "-"

        if any(keyword in title for keyword in FILTER_KEYWORDS):
            continue

        movie = Movie(title=title, votes=votes, description=description, genres=genres)
        movie.rating.mul = rating
        movies.append(movie)

    hash_movies = {movie.title: movie for movie in movies}

    print('Total movies found (+7 days from now): {}'.format(len(movies)))

    loop = asyncio.new_event_loop()
    print("Filmweb api call...")
    loop.run_until_complete(get_all_filmweb_api_data(hash_movies))
    print("IMDB api call...")
    loop.run_until_complete(get_all_imdb_api_data(hash_movies))

    movies = sort_movies_descending(movies)
    print("Saving cache...")
    save_cache(movies, MOVIES_CACHE)
    print("OK")
    return movies


if __name__ == '__main__':
    movies = get_movies(cached=True)
    print()
    for movie in movies:
        print(movie.title, movie.title_eng, (movie.rating.imdb, movie.rating.fweb), movie.poster_imdb, movie.poster_fweb, movie.runtime)
