import sys
from flask import Flask, current_app
from config import config
from flask.ext import assets
from flask.ext.socketio import SocketIO
from SPARQLWrapper import SPARQLWrapper, JSON, POST

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    config[config_name].init_app(app)

    env = assets.Environment(app)
    # where do our SASS files live?
    env.load_path = app.config["SASS"]
    env.register(
        'css_all', 
        assets.Bundle(
            'all.sass',
            filters="sass",
            output="css_all.css"
        )
    )
    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app

def create_socketio(app):
    return SocketIO(app)
