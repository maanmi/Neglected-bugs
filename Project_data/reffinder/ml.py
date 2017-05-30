
"""

"""

import os
import json
import pickle

import logging
log = logging.getLogger(__package__ + '.ml')

import numpy as np
import scipy.sparse
import sklearn.ensemble
from sklearn.feature_extraction.text import TfidfVectorizer, CountVectorizer

from . import utils
from .utils import BUGS


def get_single_model_oob():
    try:
        with open(os.path.join(utils.MODEL_DIR, 'single_rf.pickle'), 'rb') as f:
            return float(pickle.load(f).oob_score_)
    except FileNotFoundError:
        return 0


def predict_abstracts(raw, model='single'):
    X_txt_titles    = []
    X_txt_abstracts = []
    pmids = []

    for pmid, paper in raw.items():
        if paper is not None:
            X_txt_titles.append(paper['title'])
            X_txt_abstracts.append(paper['abstract'])
            pmids.append(pmid)

    vect = 'inclusive'
    if model == 'single':
        vect = 'blacklist'

    with open(os.path.join(utils.MODEL_DIR, vect + '_tv.pickle'), 'rb') as f:
        titles_vectorizer = pickle.load(f)
    with open(os.path.join(utils.MODEL_DIR, vect + '_av.pickle'), 'rb') as f:
        abstracts_vectorizer = pickle.load(f)

    X_titles = titles_vectorizer.transform(X_txt_titles)
    X_abstracts = abstracts_vectorizer.transform(X_txt_abstracts)
    X = scipy.sparse.hstack((X_titles, X_abstracts))

    with open(os.path.join(utils.MODEL_DIR, model + '_rf.pickle'), 'rb') as f:
        estimator = pickle.load(f)

    y = estimator.predict_proba(X)[:, 1].flatten()
    y_idx = np.argsort(y)[::-1]
    y = y[y_idx]
    pmids = np.array(pmids)[y_idx].tolist()
    #print(y)
    #print(pmids)

    return y, pmids


def load_abstract_cache():
    with open(utils.CACHE_FILE) as f:
        return json.load(f)


def consolidate_data(query_bug=None):
    log.info('Loading data..')
    raw = utils.load_raw_data()

    txt_titles    = []
    txt_abstracts = []

    y_engineering = []
    y_bug         = []

    cached = load_abstract_cache()

    for bug, papers in raw.items():
        for pmid, res in papers.items():
            paper = utils.retrieve_abstracts([pmid], cached=cached)[pmid]
            txt_titles.append(paper['title'])
            txt_abstracts.append(paper['abstract'])
            #
            y_engineering.append(int(res['is_eng']))
            y_bug.append(int(res['is_bug'] and bug == query_bug))

    y_engineering = np.array(y_engineering)
    y_bug = np.array(y_bug)

    return txt_titles, txt_abstracts, y_engineering, y_bug


def load_vectorizers(blacklist_bugs=False):
    model = 'blacklist' if blacklist_bugs else 'inclusive'

    with open(os.path.join(utils.MODEL_DIR, model + '_tv.pickle'), 'rb') as f:
        titles_vectorizer = pickle.load(f)
    with open(os.path.join(utils.MODEL_DIR, model + '_av.pickle'), 'rb') as f:
        abstracts_vectorizer = pickle.load(f)

    return titles_vectorizer, abstracts_vectorizer


def make_vectorizers(txt_titles, txt_abstracts, max_title_words, blacklist_bugs=True):
    log.info('Generating vectorizers..')
    stop_words = 'english'
    if blacklist_bugs:
        eng_stop_words = sklearn.feature_extraction.stop_words.ENGLISH_STOP_WORDS
        stop_words = set(eng_stop_words | set(b.lower() for b in BUGS))
        stop_words.add('lactis')
        stop_words.add('coli')

    titles_vectorizer = TfidfVectorizer(
        strip_accents='unicode',
        stop_words=stop_words,
        ngram_range=(1, 3),
        max_features=max_title_words,
    )

    abstracts_vectorizer = TfidfVectorizer(
        strip_accents='unicode',
        stop_words=stop_words,
        ngram_range=(1, 2),
        max_features=1000,
    )

    titles_vectorizer.fit(txt_titles)
    abstracts_vectorizer.fit(txt_abstracts)

    model = 'blacklist' if blacklist_bugs else 'inclusive'

    with open(os.path.join(utils.MODEL_DIR, model + '_tv.pickle'), 'wb') as f:
        pickle.dump(titles_vectorizer, f)
    with open(os.path.join(utils.MODEL_DIR, model + '_av.pickle'), 'wb') as f:
        pickle.dump(abstracts_vectorizer, f)

    return titles_vectorizer, abstracts_vectorizer


def make_targeted_model(bugname):
    titles_vectorizer, abstracts_vectorizer = load_vectorizers(blacklist_bugs=False)

    txt_titles, txt_abstracts, _, y = consolidate_data(query_bug=bugname)

    X_titles = titles_vectorizer.transform(txt_titles)
    X_abstracts = abstracts_vectorizer.transform(txt_abstracts)
    X = scipy.sparse.hstack((X_titles, X_abstracts))

    estimator = sklearn.ensemble.RandomForestClassifier(
        n_estimators=100,
        n_jobs=12,
        oob_score=True,
        random_state=13
    )

    estimator.fit(X, y)
    scores = estimator.oob_decision_function_[:, 1]
    fpr, tpr, thr = sklearn.metrics.roc_curve(y, scores)

    target_fpr = 0.1

    fpr_idx = np.argmin(np.abs(fpr - target_fpr))

    scores = {
        'acc': estimator.oob_score_,
        'tpr': tpr[fpr_idx],
        'threshold': thr[fpr_idx],
    }

    model = bugname.lower()
    with open(os.path.join(utils.MODEL_DIR, model + '_rf.pickle'), 'wb') as f:
        pickle.dump(estimator, f)
    with open(os.path.join(utils.MODEL_DIR, model + '_scores.json'), 'w') as f:
        json.dump(scores, f)


def make_single_model():
    """Generates a model to determine if a paper is an engineering paper."""
    txt_titles, txt_abstracts, y_engineering, y_bug = consolidate_data()

    max_title_words = 500
    make_vectorizers(txt_titles, txt_abstracts, max_title_words, blacklist_bugs=False)
    #
    titles_vectorizer, abstracts_vectorizer = make_vectorizers(txt_titles, txt_abstracts, max_title_words, blacklist_bugs=True)

    X_titles = titles_vectorizer.transform(txt_titles)
    X_abstracts = abstracts_vectorizer.transform(txt_abstracts)

    X = scipy.sparse.hstack((X_titles, X_abstracts))

    y = np.array(y_engineering)

    log.info('Fitting model..')

    estimator = sklearn.ensemble.RandomForestClassifier(
        n_estimators=500,
        n_jobs=12,
        oob_score=True,
        random_state=13
    )

    estimator.fit(X, y)

    with open(os.path.join(utils.MODEL_DIR, 'single_rf.pickle'), 'wb') as f:
        pickle.dump(estimator, f)

    scaled_importance = estimator.feature_importances_ / np.max(estimator.feature_importances_)

    importances = {
        'title': {w: scaled_importance[i] for w, i in titles_vectorizer.vocabulary_.items()},
        'abstract': {w: scaled_importance[i + max_title_words] for w, i in abstracts_vectorizer.vocabulary_.items()},
    }

    with open(os.path.join(utils.MODEL_DIR, 'single_imp.json'), 'w') as f:
        json.dump(importances, f)
