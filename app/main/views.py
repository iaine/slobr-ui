from flask import render_template, request, redirect, url_for, current_app
from pprint import pprint
from datetime import datetime
from SPARQLWrapper import SPARQLWrapper, JSON
from rdflib import Graph, plugin, URIRef, Literal
from rdflib.parser import Parser
from rdflib.serializer import Serializer
import json
import re

from . import main

@main.route('/index.html', methods=['GET', 'POST'])
@main.route('/episodes.html', methods=['GET', 'POST'])
@main.route('/', methods=['GET', 'POST'])
def index():
    episodes = select_episodes()
    return render_template("index.html", episodes = episodes)





def select_episodes():
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    # Get a list of all eeboo persons plus all HTRC persons who are NOT aligned to eeboo persons
    selectEpisodesQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_episodes.rq").read()
    sparql.setQuery(selectEpisodesQuery)
    sparql.setReturnFormat(JSON)
    episodeResults = sparql.query().convert()
    episodes = list()
    for e in episodeResults["results"]["bindings"]:
        date = datetime.strftime(
                 datetime.strptime(
                   e["date"]["value"][:10], #don't care about the time
                   "%Y-%m-%d"), 
                 "%A %B %d %Y"
               )
        print(date)
        episodes.append({
            "uri": e["episode"]["value"],
            "title": e["title"]["value"],
            "date": date,
            "short_synopsis": e["short_synopsis"]["value"],
            "medium_synopsis": e["medium_synopsis"]["value"],
            "long_synopsis": e["long_synopsis"]["value"],
            "image": e["image"]["value"]
            })
    return episodes[:20]


