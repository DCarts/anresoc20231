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
from orcid_service import load_orcid
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

def load_dict(file_json_path):
    if os.path.isfile(file_json_path):
        with open(file_json_path, 'r') as input_file:
            return json.load(input_file)
    else:
        return dict()

def save_dict(json_dict, file_json_path):
    json_str = json.dumps(json_dict, indent=4)
    with open(file_json_path, 'w') as output_file:
        output_file.write(json_str)

def load_authorship_from_doi(doi, doi_dict=None, doi_author_dict=None):
    if doi_dict is None:
        doi_dict = load_dict(os.path.join('data', 'doi_metadata.json'))
    if doi_author_dict is None:
        doi_author_dict = load_dict(os.path.join('data', 'doi_author.json'))


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
    return publication.get('info', {}).get('doi', None)

# authors_raw = [re.sub(', \d{4}-\d{4}-\d{4}-\d{3,4}X?', '', author_raw.strip()) for author_raw in instance['author'].split(';')]
def load_metadata_from_dois_oc(dois, doi_dict=None):
    doi_str = '__'.join(dois)

    if doi_dict is None:
        doi_dict = load_dict(os.path.join('data', 'doi_metadata.json'))

    try:
        response = requests.get(f'https://opencitations.net/index/api/v1/metadata/{doi_str}', headers={ 'Accept': 'application/json' })
        response.raise_for_status()
    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return dict()

    for instance in response.json():
        doi_dict[instance['doi']] = instance
    return doi_dict

def load_metadata_from_doi_crossref(doi, doi_dict=None):
    if doi_dict is None:
        doi_dict = load_dict(os.path.join('data', 'doi_metadata.json'))

    if doi not in doi_dict:
        raise Error(f'doi {doi} não está no dict carregado para baixar do crossref')

    if 'agency' not in doi_dict[doi] or doi_dict[doi]['agency'] != 'crossref':
        raise Error(f'doi {doi} não é do crossref para baixar do crossref')

    try:
        response = requests.get(f'https://api.crossref.org/works/{doi}', headers={ 'Accept': 'application/json' })
        response.raise_for_status()
    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()
        return doi_dict

    response_json = response.json()
    if response_json['status'] != 'ok':
        print('Erro ocorrido: {0}'.format(response['message']))
        traceback.print_exc()
        return doi_dict

    doi_dict[doi]['metadata'] = response_json
    
    return doi_dict
    
def load_agency_from_doi(doi, doi_dict=None):
    if doi_dict is None:
        doi_dict = load_dict(os.path.join('data', 'doi_metadata.json'))

    if doi not in doi_dict:
        doi_dict[doi] = dict()

    if 'agency' in doi_dict[doi]:
        return doi_dict

    try:
        response = requests.get(f'https://api.crossref.org/works/{doi}/agency', headers={ 'Accept': 'application/json' })
        response.raise_for_status()
    except Exception as err:
        print('Erro ocorrido: {0}'.format(err))
        traceback.print_exc()

    response_json = response.json()
    if response_json['status'] != 'ok':
        print('Erro ocorrido: {0}'.format(response['message']))
        traceback.print_exc()
        return doi_dict

    doi_dict[doi]['agency'] = response_json['message']['agency']['id']
    
    return doi_dict

def load_citators_from_publications(publications):

    citators_json_path = 'data/citators.json'
    citators = load_dict(citators_json_path)

    citations_json_path = 'data/citations.json'
    citations = load_dict(citations_json_path)

    doi_dict_path = os.path.join('data', 'doi_metadata.json')
    doi_dict = load_dict(doi_dict_path)

    for publication in publications:
        doi = get_doi(publication)
        if doi is None:
            continue

        if doi not in citations:
            citations[doi] = get_citing_dois_oc(doi)
            save_dict(citations, citations_json_path)
        
        citing_dois = citations.get(doi)

        new_dois = list(filter(lambda d: d not in doi_dict or 'metadata' not in doi_dict[d], citing_dois))
        if len(new_dois) > 0:
            for new_doi in new_dois:
                load_agency_from_doi(new_doi, doi_dict)
                if doi_dict[new_doi]['agency'] == 'crossref':
                    load_metadata_from_doi_crossref(new_doi, doi_dict)
                else:
                    raise Error(f'doi {new_doi} não é do crossref, é do {doi_dict[new_doi]["agency"]}')
            print('salvei')
            save_dict(doi_dict, doi_dict_path)

        # citators = load_citation_people_from_publication(publication)
        # for citator in citators:
        #     if citator in citator_maps:
        #         continue
        #     citator_map = dict()
        #     citator_maps[citator] = citator_map
        #     print('querying scholar')
        #     author = next(scholarly.search_author(citator), None)
        #     time.sleep(random.randrange(1,3))
        #     if author == None:
        #         continue
        #     citator_map['affiliation'] = author.get('affiliation', '')
        #     citator_map['email_domain'] = author.get('email_domain', '')
        # with open(citators_json_path, 'w') as output_file:
        #     output_file.write(json.dumps(citator_maps, indent=4))
    
if __name__ == '__main__':
    prepare_folders()

    # publications_list = load_conference('sbsi')
    # # load_citators_from_publications(publications_list)
    # orcid_json_path = os.path.join('data', 'orcid.json')
    # orcid_dict = load_dict(orcid_json_path)
    # # load_orcid('0000-0002-2159-339X', orcid_dict, force=True)
    # # save_dict(orcid_dict, orcid_json_path)

    # doi_meta = load_dict(os.path.join('data', 'doi_metadata.json'))
    # doi_meta_values = doi_meta.values()
    # total = 0
    # n_tem_afi_nem_orcid = 0
    # t_tem_afi = 0
    # t_tem_orcid = 0
    # tem_afi_e_orcid = 0
    # for obj in doi_meta_values:
    #     tem_afi = False
    #     tem_orcid = False
    #     for author in obj['metadata']['message']['author']:
    #         tem_afi = tem_afi or len(author['affiliation']) > 0
    #         tem_orcid = tem_orcid or 'ORCID' in author
    #         if 'ORCID' in author:
    #             load_orcid(author['ORCID'][-19:], orcid_dict)

    #     total +=1
    #     if tem_afi and tem_orcid:
    #         tem_afi_e_orcid += 1
    #     elif tem_afi:
    #         t_tem_afi += 1
    #     elif tem_orcid:
    #         t_tem_orcid += 1
    #     else:
    #         n_tem_afi_nem_orcid +=1
    # print(total, tem_afi_e_orcid, t_tem_afi, t_tem_orcid, n_tem_afi_nem_orcid)
    # save_dict(orcid_dict, orcid_json_path)

    # for publication in publications_list:
    #     if 'doi' not in publication['info']:
    #         print(publication)
    # authors = load_authors_from_publications(publications_list)
    # publications_list[:] = map(classify_publication_language_fasttext, publications_list)
    # save_conference_locally('sbsi', publications_list)
    # [print("{0} {1}: {2}".format(p['language'], publications_list.index(p), p['info']['title'])) for p in publications_list if p['language'] not in ['__label__pt', '__label__en']]

    # print(get_author_affiliations_dblp('o/JoniceOliveira'))
    

