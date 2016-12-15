import os
basedir = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'a SekRiT keY t4a7 is h4rD 2 GU3SS!1!! (cryptic sl0br!)'
    
    @staticmethod
    def init_app(app):
        pass


class DevelopmentConfig(Config): 
    DEBUG = True
    BASE_URI = "http://slobr.linkedmusic.org/" # default virtuoso port
    SPARQLUSER = "slobr"
    SPARQLPASSWORD = "slobr"
    ENDPOINT = "http://www.linkedmusic.org/sparql" # default virtuoso endpoint location
    USER = "slobr",
    SASS = basedir + "/app/sass/"
    SLOBR_QUERY_DIR = basedir + "/app/sparql/"
    EPISODE_BASE = "http://www.bbc.co.uk/programmes/"


config = {
        'development': DevelopmentConfig,
        'default': DevelopmentConfig
}
