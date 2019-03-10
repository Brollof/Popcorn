import os
import pickle

def to_float(value, decimals=1):
    if isinstance(value, str):
        value = value.replace(",", ".")
    try:
        return round(float(value), decimals)
    except:
        return 0.0

def save_cache(data, filename):
    with open(filename, 'wb') as file:
        pickle.dump(data, file)

def load_cache(filename):
    with open(filename, 'rb') as file:
        return pickle.load(file)

def get_mod_time(filename):
    if os.path.exists(filename):
        return os.path.getmtime(filename)
    return 0