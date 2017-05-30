
"""
"""

import os
import re
import json

import bs4
import requests
import matplotlib as mpl
import matplotlib.colors


BUGS = [
    'Clostridium',
    'Ruminococcus',
    'Lactobacillus',
    'Lactococcus',
    'Streptococcus',
    'Staphylococcus',
    'Listeria',
    'Escherichia',
    'Treponema',
    'Borrelia',
    'Bifidobacterium',
    'Actinomyces',
    'Mycobacterium',
    'Propionibacteria',
    'Porphyromonas',
    'Prevotella',
    'Bacteroides',
    'Fusobacterium',
    'Helicobacter',
    'Campylobacter',
    'Rickettsia',
    'Brucella',
    'Bordetella',
    'Neisseria',
    'Pseudomonas',
]


CACHE_FILE = os.path.join(os.path.dirname(__file__), 'data', 'abstract_cache.json')
DATA_FILE = os.path.join(os.path.dirname(__file__), 'data', 'data.json')
MODEL_DIR = os.path.join(os.path.dirname(__file__), 'models')


def highlight(text, vocab):
    text = text.split()

    colors = mpl.colors.LinearSegmentedColormap.from_list('clrs', ['#ffffff', '#ffcd81'])
    hilited = []

    i = 0
    n = 3
    while i < len(text):
        grams = []
        for g in range(n):
            words = ' '.join(text[i:i+g])
            if words.lower() in vocab:
                grams.append([vocab[words.lower()], words, g])

        if grams:
            imp, words, g = max(grams)
            clr = mpl.colors.to_hex(colors(imp))
            hilited.append('<span style="background-color:{};">{}</span>'.format(clr, words))
            i += g
        else:
            hilited.append(text[i])
            i += 1

    return ' '.join(hilited)


def load_raw_data():
    with open(DATA_FILE) as f:
        return json.load(f)


def retrieve_abstracts(id_list, cached=None):
    if cached is None:
        with open(CACHE_FILE) as f:
            cached = json.load(f)

    new_articles = [pmid for pmid in id_list if pmid not in cached]

    if new_articles:
        db = 'pubmed'
        base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

        #print('Fetching', len(new_articles), 'new abstracts..')

        url = base + 'epost.fcgi?db={}'.format(db)
        req = requests.post(url, data={'id': ','.join(new_articles)})
        soup = bs4.BeautifulSoup(req.text, 'lxml-xml')

        try:
            key = soup.find('QueryKey').text
            web = soup.find('WebEnv').text
        except AttributeError:
            print(soup)
            raise

        for i in range(0, len(new_articles), 10000):
            #print('From index', i)
            url = base + 'efetch.fcgi?db={}&query_key={}&WebEnv={}&rettype=xml&retmode=xml&retstart={}'.format(db, key, web, i)
            req = requests.get(url)
            soup = bs4.BeautifulSoup(req.text, 'lxml-xml')

            for art in soup.find_all('PubmedArticle'):
                pmid = art.find('PMID').text
                title = art.find('ArticleTitle').text
                abstract = art.find('AbstractText')
                if abstract:
                    cached[pmid] = {'title': title, 'abstract': abstract.text, 'pmid': pmid}
                else:
                    cached[pmid] = None

        not_found = set(new_articles) - set(cached)
        #print('Not found:', len(not_found))
        for pmid in not_found:
            cached[pmid] = None

        with open(CACHE_FILE, 'w') as f:
            json.dump(cached, f)

    subset = {}
    for pmid in id_list:
        if pmid in cached:
            subset[pmid] = cached[pmid]
        else:
            subset[pmid] = None

    return subset


def get_abstracts(query, retmax, blacklist):
    db = 'pubmed'
    base = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/'

    rm = 100000

    url = base + 'esearch.fcgi?db={}&term={}&retmax={}&usehistory=y'.format(db, query, rm)
    req = requests.get(url)
    soup = bs4.BeautifulSoup(req.text, 'lxml-xml')
    id_list = [pmid.text for pmid in soup.find('IdList').find_all('Id')]

    count = int(soup.find('Count').text)
    #print('Found', count, 'ids..')
    if count > rm:
        webenv = soup.find('WebEnv').text
        for i in range(1, int(count / rm) + 1):
            #print(i)
            url = base + 'esearch.fcgi'
            params = {'db': db, 'term': query, 'retmax': rm, 'retstart': i * rm,
                'usehistory': 'y', 'WebEnv': webenv}
            req = requests.get(url, params=params)
            soup = bs4.BeautifulSoup(req.text, 'lxml-xml')
            id_list.extend([pmid.text for pmid in soup.find('IdList').find_all('Id')])
            #break

    cached = retrieve_abstracts(id_list)

    pmids = []
    for pmid in id_list:
        if pmid in blacklist:
            continue
        if pmid in cached and cached[pmid]:
            pmids.append(pmid)
        if retmax and len(pmids) >= retmax:
            break

    return pmids
