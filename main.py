import requests
import math
import json
import os
import fasttext
import xml.etree.ElementTree as ET
import traceback
import re
from scholarly import scholarly
import random
import time
fasttext_model = fasttext.load_model('lid.176.ftz')

def download_conference(conference_alias):
    publications = []
    try:
        response = requests.get('https://dblp.org/search/publ/api?q=stream:conf/{0}:&format=json&h=0'.format(conference_alias))
        response.raise_for_status()
        publications_count = int(response.json()['result']['hits']['@total'])
        h = 100
        for f in range(int(math.ceil(publications_count/h))):
            response = requests.get('https://dblp.org/search/publ/api?q=stream:conf/{0}:&format=json&h={1}&f={2}'.format(conference_alias, h, f*h))
            response.raise_for_status()
            publications = publications + response.json()['result']['hits']['hit']

    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return None
    
    publications[:] = map(classify_publication_language, publications)
    return publications

def save_conference_locally(conference_alias, conference=None):
    if conference is None:
        conference = download_conference(conference_alias)
    conference_json = json.dumps(conference, indent=4)
    with open('conferences/{0}.json'.format(conference_alias), 'w') as output_file:
        output_file.write(conference_json)

def load_conference(conference_alias, force=False):
    if force or not os.path.isfile('conferences/{0}.json'.format(conference_alias)):
        save_conference_locally(conference_alias)
    with open('conferences/{0}.json'.format(conference_alias), 'r') as input_file:
        return json.load(input_file)

def classify_publication_language_fasttext(publication):
    language = fasttext_model.predict(publication['info']['title'].split('[')[0], k=1)[0][0]
    publication['language'] = language
    return publication

def classify_publication_language(publication):
    return classify_publication_language_fasttext(publication)

def prepare_folders():
    os.makedirs('conferences', exist_ok = True)
    os.makedirs('authors', exist_ok = True)
    os.makedirs('data', exist_ok = True)

def get_author_affiliations_dblp(author_pid):
    try:
        response = requests.get(f'https://dblp.org/pid/{author_pid}.xml', headers={ 'Accept': 'application/xml' })
        response.raise_for_status()
        tree = ET.ElementTree(ET.fromstring(response.content))
        notes = tree.findall("person/note[@type='affiliation']")
        return [note.text for note in notes]

    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return []

def get_author_pids(publication):
    author_maps = publication['info']['authors']['author']
    try:
        return [author_map['@pid'] for author_map in author_maps]
    except KeyError as err:
        print(author_maps)
        raise err

def load_authors_from_publications(publications):
    authors_json_path = 'authors/authors.json'
    if os.path.isfile(authors_json_path):
        with open(authors_json_path, 'r') as input_file:
            author_map = json.load(input_file)
    else:
        author_map = dict()

    for publication in publications:
        pids = get_author_pids(publication)
        for pid in pids:
            if pid not in author_map:
                author_map[pid] = set()
                affiliations = get_author_affiliations_dblp(pid)
    return author_map

load_dict(file_json_path):
    if os.path.isfile(file_json_path):
        with open(file_json_path, 'r') as input_file:
            return json.load(input_file)
    else:
        return dict()

save_dict(json_dict, file_json_path):
    json_str = json.dumps(json_dict, indent=4)
    with open(file_json_path, 'w') as output_file:
        output_file.write(json_str)

def get_citing_dois_oc(doi):
    try:
        response = requests.get(f'https://opencitations.net/index/api/v1/citations/{doi}', headers={ 'Accept': 'application/json' })
        response.raise_for_status()
    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return list()

    citations = [citation['citing'] for citation in response.json()]

    if len(citations) == 0:
        return list()

    citing_dois = set()
    for citation in citations:
        citing_dois.update([x.split('=>')[1].strip() for x in citation.split(';')])

    return list(citing_dois)

def get_doi(publication):

def get_author_names_from_dois_oc(dois):
    doi_str = '__'.join(citing_dois)

    try:
        response = requests.get(f'https://opencitations.net/index/api/v1/metadata/{doi_str}', headers={ 'Accept': 'application/json' })
        response.raise_for_status()
    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return dict()

    authors = dict()
    for instance in response.json():
        authors_raw = [re.sub(', \d{4}-\d{4}-\d{4}-\d{3,4}X?', '', author_raw.strip()) for author_raw in instance['author'].split(';')]
        authors[instance['doi']] = authors_raw
    return authors
    
def load_citators_from_publications(publications):

    citators_json_path = 'data/citators.json'
    citators = load_dict(citators_json_path)

    citations_json_path = 'data/citations.json'
    citations = load_dict(citations_json_path)

    for publication in publications:
        doi = get_doi(publication)
        if doi is None:
            continue

        if doi not in citations:
            citations[doi] = get_citing_dois_oc(doi)
            save_dict(citations, citations_json_path)
        
        citing_dois = citations.get(doi)

        citators = load_citation_people_from_publication(publication)
        for citator in citators:
            if citator in citator_maps:
                continue
            citator_map = dict()
            citator_maps[citator] = citator_map
            print('querying scholar')
            author = next(scholarly.search_author(citator), None)
            time.sleep(random.randrange(1,3))
            if author == None:
                continue
            citator_map['affiliation'] = author.get('affiliation', '')
            citator_map['email_domain'] = author.get('email_domain', '')
        with open(citators_json_path, 'w') as output_file:
            output_file.write(json.dumps(citator_maps, indent=4))


    return citator_maps
    
if __name__ == '__main__':
    prepare_folders()
    publications_list = load_conference('sbsi')
    load_citators_from_publications(publications_list)
    # for publication in publications_list:
    #     if 'doi' not in publication['info']:
    #         print(publication)
    # authors = load_authors_from_publications(publications_list)
    # publications_list[:] = map(classify_publication_language_fasttext, publications_list)
    # save_conference_locally('sbsi', publications_list)
    # [print("{0} {1}: {2}".format(p['language'], publications_list.index(p), p['info']['title'])) for p in publications_list if p['language'] not in ['__label__pt', '__label__en']]

    # print(get_author_affiliations_dblp('o/JoniceOliveira'))
    

