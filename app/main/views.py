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

@main.route('/index', methods=['GET', 'POST'])
@main.route('/episodes', methods=['GET', 'POST'])
@main.route('/', methods=['GET', 'POST'])
def index():
    episodes = select_episodes()
    return render_template("index.html", episodes = episodes)

@main.route('/episode', methods=['GET', 'POST'])
def episode(): 
    if request.args.get('pid'):
        episode = select_episodes(request.args.get('pid'))[0]
        segments = select_segments_by_episode(request.args.get('pid'))
        segContrib = select_contributors_by_segments(segments)
        return render_template("episode.html", episode = episode, segContrib = segContrib)
    else:
        return redirect(url_for('.index'))



def select_episodes(pid=None):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    selectEpisodesQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_episodes.rq").read()
    if pid is None:
        selectEpisodesQuery = selectEpisodesQuery.format(uri = "")
    else:
        selectEpisodesQuery = selectEpisodesQuery.format(uri = "BIND(<" + pid + "> as ?uri) .")
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
        epResults = {
            "uri": e["uri"]["value"],
            "pid": e["uri"]["value"].replace("http://slobr.linkedmusic.org/", ""),
            "title": e["title"]["value"],
            "date": date,
            "short_synopsis": e["short_synopsis"]["value"],
            "medium_synopsis": e["medium_synopsis"]["value"],
            "long_synopsis": e["long_synopsis"]["value"],
            "image": e["image"]["value"].replace("http://slobr.linkedmusic.org/bbcimages/", "")
        }
        if "nextEpisode" in e:
            epResults["nextEpisode"] = e["nextEpisode"]["value"] 
        if "previousEpisode" in e:
            epResults["previousEpisode"] =  e["previousEpisode"]["value"]
        episodes.append(epResults)
    return episodes


def select_segments_by_episode(episodePid):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    selectSegmentsQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_segments_by_episode.rq").read()
    selectSegmentsQuery = selectSegmentsQuery.format(uri = "BIND(<" + episodePid + "> as ?uri) .")
    print selectSegmentsQuery
    sparql.setQuery(selectSegmentsQuery)
    sparql.setReturnFormat(JSON)
    segmentResults = sparql.query().convert()
    pprint(segmentResults)
    segments = list()
    for s in segmentResults["results"]["bindings"]:
        segments.append({
            "segEvents": s["segEvents"]["value"],
            "segEventsPosition": s["segEventsPosition"]["value"],
            "segment": s["segment"]["value"]
            })
    return segments 

def select_contributors_by_segments(segments):   
    app = current_app._get_current_object()
    segids = ""
    for s in segments:
        # following weirdness is because SPARQL (or Virtuoso?) doesn't seem to like
        # VALUES parameters with expanded URIs
        segids +=  "bbc:" + s["segment"].replace(app.config["EPISODE_BASE"], "") + "\n"
    if not segids:
        return None # some episodes don't have segments
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    selectContributorsQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_contributors_by_segments.rq").read()
    selectContributorsQuery = selectContributorsQuery.format(segments=segids)
    sparql.setQuery(selectContributorsQuery)
    sparql.setReturnFormat(JSON)
    contributorResults = sparql.query().convert()
    segments = dict()
    for s in contributorResults["results"]["bindings"]:
        segid = s["segment"]["value"]
        if segid not in segments:
            segments[segid] = { 
                "title": s["title"]["value"],
                "contributors" : list()
            }
        segments[segid]["contributors"].append({
            "contributorUri": s["contributor"]["value"],
            "contributorName": s["name"]["value"]
        })

    return segments
