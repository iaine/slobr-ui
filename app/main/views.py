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
    targets = None
    # if a source episode is provided, only list the episodes that share contributors with the source
    if request.args.get('contributorSource'):
        targets = select_same_contributor_episodes(request.args.get('contributorSource'))
    elif request.args.get('contributor'):
        targets = select_this_contributor_episodes(request.args.get('contributor').split("|"))
    episodes = select_episodes(targets)
    return render_template("index.html", episodes = episodes)

@main.route('/episode', methods=['GET', 'POST'])
def episode(): 
    if request.args.get('pid'):
        episode = select_episodes([request.args.get('pid')])[0]
        segments = select_segments_by_episode(request.args.get('pid'))
        segContrib = select_contributors_by_segments(segments)
        return render_template("episode.html", episode = episode, segContrib = segContrib)
    else:
        return redirect(url_for('.index'))


@main.route('/work', methods=['GET', 'POST'])
def work():
    if request.args.get('workid'):
        work = select_blob(request.args.get('workid'))
#        print "Got work:"
#        print json.dumps(work, indent=4)
        contributors = select_contributors(work["dct:contributor"])
#        print contributors 
        if "dct:isPartOf" in work:
            images = select_images_by_book(work["dct:isPartOf"])
        else:
            images = None
#        print "Got back work:"
#        print json.dumps(work, indent=4)
        return render_template("work.html", work = work, images = images, contributors = contributors)
    else:
        return redirect(url_for('.index'))

@main.route('/contributor', methods=['GET', 'POST'])
def contributor():
    if request.args.get('contributor'):
        contributor = select_blob(request.args.get('contributor'))
        emsuri = None
        external = None
        contemporaries = None
        mbz = None
        works = None
#        print "Got back contributor:"
#        print json.dumps(contributor, indent=4)
        #find the EMS uri
        for uri in contributor["salt:uri"]: 
            if uri.startswith("http://slobr.linkedmusic.org"):
                emsuri = uri
        if emsuri:
            works = select_contributor_work_episodes(emsuri)
        if "slobr:linkedbrainz_uri" in contributor:
            mbz = contributor["slobr:linkedbrainz_uri"]
        elif "mo:musicbrainz_guid" in contributor:
            mbz = contributor["mo:musibrainz_guid" + "#_"]
        if mbz:
            try: 
                external = select_external_contributor(mbz, reduced = False)
                if not external:
                    external = select_external_contributor(mbz, reduced = True)
#                print json.dumps(external, indent=4)
                contemporaries = select_contemporaries(external["birth"], external["death"])

            except:
                pass
        return render_template("contributor.html", contributor=contributor, external=external, contemporaries = contemporaries, works = works)
    else:
        return redirect(url_for('.index'))


def select_blob(uri):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_blob.rq").read()
    # FIXME figure out the trusted graph cleverly
    trustedGraph = "http://slobr.linkedmusic.org/matchDecisions/DavidLewis"
    #trustedGraph = "http://slobr.linkedmusic.org/matchDecisions"
    selectQuery = selectQuery.format(sourceUri = uri,trustedGraph = trustedGraph)
#    print selectQuery
    sparql.setQuery(selectQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    extracted = dict()
    for r in results["results"]["bindings"]:
        if "salt:uri" not in extracted:
            extracted["salt:uri"] = list()
        if r["p"]["value"] not in extracted:
            extracted[r["p"]["value"]] = list()
        extracted[r["p"]["value"]].append(r["o"]["value"])
        if r["uri"]["value"] not in extracted["salt:uri"]:
            extracted["salt:uri"].append(r["uri"]["value"])

    context = { 
        "mo": "http://purl.org/ontology/mo/",
        "po": "http://purl.org/ontology/po/",
        "slobr": "http://slobr.linkedmusic.org/terms/",
        "dct": "http://purl.org/dc/terms/",
        "salt": "http://slobr.linkedmusic.org/salt/",
        "saltset": "http://slobr.linkedmusic.org/saltset/",
        "contrib": "http://slobr.linkedmusic.org/contributors/",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#"
    }

    g = Graph().parse(data=json.dumps(extracted), format="json-ld")
    blob = g.serialize(format="json-ld", auto_compact=True, context=context, indent=4)
    return json.loads(blob)
    
def select_episodes(episodePids=None):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectEpisodesQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_episodes.rq").read()
    if episodePids is None:
        selectEpisodesQuery = selectEpisodesQuery.format(uri = "")
    else:
        epVals = "VALUES ?uri { \n"
        for ep in episodePids:
            # following weirdness is because SPARQL (or Virtuoso?) doesn't seem to like
            # VALUES parameters with expanded URIs
            epVals += "<" + ep + ">\n"
        epVals += "}"
        selectEpisodesQuery = selectEpisodesQuery.format(uri = epVals)
    sparql.setQuery(selectEpisodesQuery)
    #print selectEpisodesQuery
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
    sparql.setTimeout(3)
    selectSegmentsQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_segments_by_episode.rq").read()
    selectSegmentsQuery = selectSegmentsQuery.format(uri = "BIND(<" + episodePid + "> as ?uri) .")
    sparql.setQuery(selectSegmentsQuery)
    sparql.setReturnFormat(JSON)
    segmentResults = sparql.query().convert()
    segments = list()
    for s in segmentResults["results"]["bindings"]:
        segEventPosition = s["segEventsPosition"] if "segEventPosition" in s else None
        segments.append({
            "segEvents": s["segEvents"]["value"],
            "segEventsPosition": segEventPosition,
            "segment": s["segment"]["value"]
            })
    return segments 

def select_contributors(contrib):
    app = current_app._get_current_object()
    contributor = "VALUES ?contributor { \n"
    # following weirdnesses is because SPARQL (or Virtuoso?) doesn't seem to like
    # VALUES parameters with expanded URIs
    if isinstance(contrib, basestring):
        contributor += contrib.replace("http://slobr.linkedmusic.org/contributors/", "contr:")  + "\n"
    else:
        for c in contrib:
            contributor += c.replace("http://slobr.linkedmusic.org/contributors/", "contr:") + "\n"
    contributor += "}"
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectContributorsQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_contributors.rq").read()
    selectContributorsQuery = selectContributorsQuery.format(contributor = contributor)
    sparql.setQuery(selectContributorsQuery)
    sparql.setReturnFormat(JSON)
    contributorResults = sparql.query().convert()
    contributors = dict()
    for cR in contributorResults["results"]["bindings"]:
        contributors[cR["contributor"]["value"]] = cR["name"]["value"]
    return contributors

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
    sparql.setTimeout(3)
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


def select_same_contributor_episodes(sourceEpisode):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectContributorsQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_same_contributor_episodes.rq").read()
    sourceEpisode = "BIND(<" + sourceEpisode + "> as ?sourceEpisode) ."
    selectContributorsQuery = selectContributorsQuery.format(sourceEpisode = sourceEpisode)
    sparql.setQuery(selectContributorsQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    episodes = list()
    for r in results["results"]["bindings"]:
        episodes.append(r["targetEpisode"]["value"])
    return episodes 

def select_this_contributor_episodes(contributors):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectEpisodesQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_this_contributor_episodes.rq").read()
    contributor = "VALUES ?contributor { \n"
    for c in contributors:
        # following weirdness is because SPARQL (or Virtuoso?) doesn't seem to like
        # VALUES parameters with expanded URIs
        contributor += "<" + c + ">\n"
    contributor += "}"
    selectEpisodesQuery = selectEpisodesQuery.format(contributor = contributor)
    sparql.setQuery(selectEpisodesQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    episodes = list()
    for r in results["results"]["bindings"]:
        episodes.append(r["targetEpisode"]["value"])
    return episodes 

def select_images_by_book(books):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectImagesQuery = open(app.config["SLOBR_QUERY_DIR"] + "select_images_by_book.rq").read()
    b = "VALUES ?book { \n" 
    for book in books:
        b += "<" + book + ">\n"
    b += " }"
    selectImagesQuery = selectImagesQuery.format(book = b)
    sparql.setQuery(selectImagesQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    images = list()
    for r in results["results"]["bindings"]:
        #TODO FIXME ugly hack to take care of EMO ridiculousness -- fix in the triples once this is confirmed as permanent
        images.append(r["image"]["value"].replace("digirep.rhul.ac.uk", "repository.royalholloway.ac.uk"))
    return images 

def select_external_contributor(linkedbrainz, reduced):
    if reduced: # try to get just the most basic details (birth/death dates, depiction, bio)
        template = "select_external_reduced_contributor.rq"
    else:
        template = "select_external_contributor.rq"
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectExternalQuery = open(app.config["SLOBR_QUERY_DIR"] + template).read()
    linkedbrainz = "BIND(<" + linkedbrainz + ">as ?linkedbrainz) ."
    selectExternalQuery = selectExternalQuery.format(linkedbrainz = linkedbrainz)
#    print "External query: "+ selectExternalQuery
    sparql.setQuery(selectExternalQuery)
#    print selectExternalQuery
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    external = dict()
    for r in results["results"]["bindings"]:
        for key in r:
            external[key] = r[key]["value"]
    return external 

def select_contemporaries(birthYear, deathYear):
    # return books that were published between (a composer's) birthYear and deathYear
    # along with information on those books' authors
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectContemporariesQuery= open(app.config["SLOBR_QUERY_DIR"] + "select_contemporaries.rq").read()
    selectContemporariesQuery = selectContemporariesQuery.format(
        birthYear = birthYear[:4],
        deathYear = deathYear[:4]
    )
    sparql.setQuery(selectContemporariesQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    contemporaries = list()
    for r in results["results"]["bindings"]:
        c = dict()
        for key in r:
            c[key] = r[key]["value"]
        contemporaries.append(c)
    return contemporaries 
 
def select_contributor_work_episodes(contributor):
    app = current_app._get_current_object()
    sparql = SPARQLWrapper(app.config["ENDPOINT"])
    sparql.setCredentials(user = app.config["SPARQLUSER"], passwd = app.config["SPARQLPASSWORD"])
    sparql.setTimeout(3)
    selectContributorWorksQuery= open(app.config["SLOBR_QUERY_DIR"] + "select_contributor_work_episodes.rq").read()
    selectContributorWorksQuery = selectContributorWorksQuery.format(
        contributor = contributor
    )
    sparql.setQuery(selectContributorWorksQuery)
    sparql.setReturnFormat(JSON)
    results = sparql.query().convert()
    contributerWorks = list()
    for r in results["results"]["bindings"]:
        c = dict()
        for key in r:
            c[key] = r[key]["value"]
        contributerWorks.append(c)
    return contributerWorks 
