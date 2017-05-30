
"""

"""

import os
import re
import sys
import json
import logging

import flask
import numpy as np

sys.path.append('.')

from . import utils
from . import ml
from .utils import BUGS

app = flask.Flask(__package__)
app.secret_key = 'secret for real'

# handler = logging.StreamHandler(sys.stdout)
# app.logger.addHandler(handler)
app.logger.setLevel(logging.DEBUG)

PMIDS_PER_SEARCH = 100

@app.route('/')
def index():
    raw = utils.load_raw_data()

    vals = {'bugs': [], 'scores': {}, 'total': {}, 'pos': {}}

    for b in BUGS:
        vals['total'][b] = len(raw.get(b, []))
        vals['pos'][b] = sum([d['is_eng'] and d['is_bug'] for p,d in raw.get(b, {}).items()])
        vals['bugs'].append(b)

        scorefile = os.path.join(utils.MODEL_DIR, b.lower() + '_scores.json')

        vals['scores'][b] = 'N/A'
        if os.path.isfile(scorefile):
            with open(scorefile) as f:
                bugscores = json.load(f)
                vals['scores'][b] = '{:.2%}'.format(bugscores['tpr'])

    vals['single_model_score'] = '{:.3f}'.format(ml.get_single_model_oob())

    return flask.render_template('index.html', **vals)


@app.route('/genmdl')
def generate_single_model():
    ml.make_single_model()
    return flask.redirect(flask.url_for('index'))

@app.route('/naivebug/<bugname>', methods=['GET', 'POST'])
def naivebug(bugname):
    vals = {}
    vals['current_bug'] = bugname

    bugdata = utils.load_raw_data().get(bugname, {})
    blacklist = set(bugdata)

    flask.session['current_bug'] = bugname
    flask.session['probas'] = None

    query = bugname + ' AND (engineer OR crispr OR transformation OR vector OR recombinant)'

    flask.session['pmids'] = utils.get_abstracts(query, PMIDS_PER_SEARCH, blacklist)
    print('Got abstracts:', len(flask.session['pmids']))
    #flask.session['pmidx'] = 0

    newurl = flask.url_for('paper',
        bugname=bugname,
        pmid=flask.session['pmids'][0],
        mode='naive',
    )
    return flask.redirect(newurl)


def save_paper():
    data = utils.load_raw_data()
    bugpost = flask.request.form['bugname']
    if bugpost not in data:
        data[bugpost] = {}

    data[bugpost][flask.request.form['pmid']] = {
        'is_bug': flask.request.form['isBug'] == 'true',
        'is_eng': flask.request.form['isEng'] == 'true',
    }

    with open(utils.DATA_FILE, 'w') as f:
        json.dump(data, f)

    return data

@app.route('/paper/<mode>/<bugname>/<pmid>', methods=['GET', 'POST'])
def paper(bugname, pmid, mode):
    if flask.request.method == 'POST':
        data = save_paper()
        return flask.redirect(flask.url_for('paper',
            bugname=bugname,
            pmid=pmid,
            mode=mode))
    else:
        data = utils.load_raw_data()

    vals = {}
    vals['current_bug'] = bugname
    next_bugidx = BUGS.index(vals['current_bug']) + 1
    vals['next_bug'] = BUGS[next_bugidx if next_bugidx < len(BUGS) else 0]
    vals['next_url'] = flask.url_for(mode + 'bug', bugname=vals['next_bug'])

    if pmid == '0':
        return flask.redirect(vals['next_url'])

    vals['pmid'] = pmid

    pmidx = flask.session['pmids'].index(pmid)
    if pmidx >= PMIDS_PER_SEARCH or pmidx >= len(flask.session['pmids']) - 1:
        vals['return_url'] = flask.url_for('paper',
            bugname=bugname, pmid='0', mode=mode)
    else:
        vals['return_url'] = flask.url_for('paper',
            bugname=bugname, pmid=flask.session['pmids'][pmidx + 1], mode=mode)

    bugdata = data.get(bugname, {})
    vals['n'] = len(bugdata)
    vals['pos'] = sum([d['is_eng'] and d['is_bug'] for d in bugdata.values()])

    abstract = utils.retrieve_abstracts([pmid])[pmid]

    hilite_weights_ttl = {bugname.lower(): 1.}
    hilite_weights_ab = {bugname.lower(): 1.}

    if flask.session.get('vocab'):
        with open(flask.session.get('vocab'), 'rb') as f:
            vocab = json.load(f)
        hilite_weights_ttl.update(vocab['title'])
        hilite_weights_ab.update(vocab['abstract'])

    vals['title'] = utils.highlight(abstract['title'], hilite_weights_ttl)
    vals['abstract'] = utils.highlight(abstract['abstract'], hilite_weights_ab)

    vals['proba'] = 'N/A'
    if flask.session.get('probas'):
        vals['proba'] = flask.session['probas'][pmidx]

    vals['bugs'] = BUGS

    return flask.render_template('bug.html', **vals)


@app.route('/singlebug/<bugname>', methods=['GET', 'POST'])
def singlebug(bugname):
    vals = {}
    vals['current_bug'] = bugname

    bugdata = utils.load_raw_data().get(bugname, {})
    blacklist = set(bugdata)

    flask.session['current_bug'] = bugname

    all_pmids = utils.get_abstracts(bugname, None, blacklist)
    print('Got abstracts:', len(all_pmids))
    abstracts = utils.retrieve_abstracts(all_pmids)

    if not abstracts:
        return flask.redirect(flask.url_for('paper',
            bugname=bugname, pmid='0', mode='single'))

    y, pmids = ml.predict_abstracts(abstracts)

    flask.session['pmids'] = pmids[:PMIDS_PER_SEARCH]
    flask.session['probas'] = ['E: {:.1%}'.format(p) for p in y.tolist()[:PMIDS_PER_SEARCH]]
    flask.session['vocab'] = os.path.join(utils.MODEL_DIR, 'single_imp.json')

    newurl = flask.url_for('paper',
        bugname=bugname,
        pmid=flask.session['pmids'][0],
        mode='single',
    )
    return flask.redirect(newurl)


@app.route('/fit/<bugname>')
def fitbug(bugname):
    ml.make_targeted_model(bugname)
    return flask.redirect(flask.url_for('index'))


@app.route('/targetedbug/<bugname>', methods=['GET', 'POST'])
def targetedbug(bugname):
    vals = {}
    vals['current_bug'] = bugname

    bugdata = utils.load_raw_data().get(bugname, {})
    blacklist = set(bugdata)

    flask.session['current_bug'] = bugname

    all_pmids = utils.get_abstracts(bugname, None, blacklist)
    print('Got abstracts:', len(all_pmids))
    abstracts = utils.retrieve_abstracts(all_pmids)

    if not abstracts:
        return flask.redirect(flask.url_for('paper',
            bugname=bugname, pmid='0', mode='single'))


    eng_preds = {pmid: pred for pred, pmid in zip(*ml.predict_abstracts(abstracts, model='single'))}
    bug_preds = {pmid: pred for pred, pmid in zip(*ml.predict_abstracts(abstracts, model=bugname.lower()))}

    tot_preds = {pmid: (eng_p, bug_preds[pmid]) for pmid, eng_p in eng_preds.items()}
    pmids, preds = zip(*sorted(tot_preds.items(), key=lambda x: x[1][0] + x[1][1] * 3, reverse=True))

    pmids = pmids[:PMIDS_PER_SEARCH]
    preds = preds[:PMIDS_PER_SEARCH]

    flask.session['pmids'] = pmids
    flask.session['probas'] = ['E: {:.1%} B: {:.1%}'.format(*p) for p in preds]
    flask.session['vocab'] = os.path.join(utils.MODEL_DIR, 'single_imp.json')

    newurl = flask.url_for('paper',
        bugname=bugname,
        pmid=flask.session['pmids'][0],
        mode='targeted',
    )
    return flask.redirect(newurl)

#if __name__ == '__main__':
#    app.run(debug=True)
