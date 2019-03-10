from rating import Rating

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
        self.runtime = 0

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