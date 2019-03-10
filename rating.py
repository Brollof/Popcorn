from utils import to_float

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