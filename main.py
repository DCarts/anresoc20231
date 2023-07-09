import requests
import math
import json
import os
import fasttext
import openpyxl
import xml.etree.ElementTree as ET
import traceback
import re
from scholarly import scholarly
import random
import time
#from orcid_service import load_orcid
import iso3166
fasttext_model = fasttext.load_model('lid.176.ftz')

#Muzy
import pandas as pd
import html

REMOVE_ACCENTS_TRANSLATION = str.maketrans('áéíóúàèìòùãõâêîôû', 'aeiouaeiouaoaeiou')
COUNTRIES_CASEFOLDED = tuple([x.casefold() for x in iso3166.countries_by_name.keys()] + ['united states', 'iran', 'united kingdom', 'turkey', 'itally', 'russia'])
BRAZILIAN_STATES_CASEFOLDED = tuple(x.casefold() for x in ['Acre',
'alagoas',
'amapa',
'amazonas',
'bahia',
'Ceara',
'Distrito Federal',
'Espirito Santo',
'Goias',
'Maranhao',
'Mato Grosso',
'Mato Grosso do Sul',
'Minas Gerais',
'Para',
'Paraiba',
'Parana',
'Pernambuco',
'Piaui',
'Rio de Janeiro',
'Rio Grande do Norte',
'Rio Grande do Sul',
'Rondonia',
'Roraima',
'Santa Catarina',
'Sao Paulo',
'Sergipe',
'Tocantins'])

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

def get_citing_dois_ss(doi):
    try:
        response = requests.get(f'https://api.semanticscholar.org/v1/paper/{doi}', headers={ 'Accept': 'application/json' })
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
    
def clean_affiliation(affiliation):
    return affiliation.casefold().translate(REMOVE_ACCENTS_TRANSLATION).strip('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    
def load_affiliation_related_to_portuguese(affiliation, affiliation_dict=None):
    affiliation = affiliation.casefold().translate(REMOVE_ACCENTS_TRANSLATION).strip('!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~')
    if affiliation_dict is None:
        affiliation_dict = load_dict(os.path.join('data', 'affiliations.json'))

    if affiliation in affiliation_dict:
        return affiliation_dict[affiliation]

    if affiliation.endswith(('brasil', 'brazil')) or any(x in affiliation for x in BRAZILIAN_STATES_CASEFOLDED + ('brasil', 'brazil')):
        affiliation_dict[affiliation] = True
    elif affiliation.endswith(COUNTRIES_CASEFOLDED):
        affiliation_dict[affiliation] = False
    else:
        print('A afiliação com nome')
        print(f'"{affiliation}"') 
        print('é relacionada à lingua portuguesa?')
        valid_yes_answers = ['s', 'sim', 'y', 'yes']
        valid_no_answers = ['n', 'no', 'nao']
        answer = ''
        while answer not in valid_yes_answers + valid_no_answers:
            answer = input("(s/n) ").casefold()

        affiliation_dict[affiliation] = answer in valid_yes_answers
    return affiliation_dict[affiliation]

def load_orcid_related_to_portuguese(orcid, orcid_dict=None):
    if orcid_dict is None:
        orcid_dict = load_dict(os.path.join('data', 'orcid.json'))
    if orcid not in orcid_dict: # carrega orcid no orcid_dict
        load_orcid(orcid, orcid_dict, method='person')
        load_orcid(orcid, orcid_dict, method='employment')
    if 'related_to_portuguese' in orcid_dict[orcid]:
        return orcid_dict[orcid]
    
    if 'person' in orcid_dict[orcid]:
        person_dict = orcid_dict[orcid].get('person', dict())
        if type(person_dict) is not dict:
            person_dict = dict()

        addresses_dict = person_dict.get('addresses', dict())
        if type(addresses_dict) is not dict:
            addresses_dict = dict()

        addresses_list = addresses_dict.get('address', [])
        if type(addresses_list) is not list:
            addresses_list = list()

        if len(addresses_list) > 0:
            for address in addresses_list:
                country_dict = address.get('country', dict())
                if type(country_dict) is not dict:
                    country_dict = dict()
                country_code = country_dict.get('value', None)
                if country_code in ('AO', 'BR', 'CV', 'GW', 'MZ', 'PT', 'ST'):
                    orcid_dict[orcid]['related_to_portuguese'] = True
                    return orcid_dict
                    

            orcid_dict[orcid]['related_to_portuguese'] = False
            return orcid_dict
            
        employments_dict = orcid_dict[orcid].get('employments', dict())
        if type(employments_dict) is not dict:
            employments_dict = dict()

        employments_list = employments_dict.get('employment-summary', [])
        if type(employments_list) is not list:
            employments_list = list()

        if len(employments_list) > 0:
            for employment in employments_list:
                organization_dict = employment.get('organization', dict())
                if type(organization_dict) is not dict:
                    organization_dict = dict()
                address_dict = organization_dict.get('address', dict())
                if type(address_dict) is not dict:
                    address_dict = dict()
                country_code = address_dict.get('value', None)
                if country_code in ('AO', 'BR', 'CV', 'GW', 'MZ', 'PT', 'ST'):
                    orcid_dict[orcid]['related_to_portuguese'] = True
                    return orcid_dict
            orcid_dict[orcid]['related_to_portuguese'] = False
            return orcid_dict
        
        biography_dict = person_dict.get('biography', dict())
        if type(biography_dict) is not dict:
            biography_dict = dict()
        content_str = biography_dict.get('content', None)
        if type(content_str) is str:
            content_str = clean_affiliation(content_str)
            if content_str.endswith(('brasil', 'brazil')) or any(x in content_str for x in BRAZILIAN_STATES_CASEFOLDED + ('brasil', 'brazil')):
                orcid_dict[orcid]['related_to_portuguese'] = True
                return orcid_dict
            elif content_str.endswith(COUNTRIES_CASEFOLDED):
                orcid_dict[orcid]['related_to_portuguese'] = False
                return orcid_dict
            else:
                print('A biografia')
                print(f'"{content_str}"') 
                print('é relacionada à lingua portuguesa?')
                valid_yes_answers = ['s', 'sim', 'y', 'yes']
                valid_no_answers = ['n', 'no', 'nao']
                answer = ''
                while answer not in valid_yes_answers + valid_no_answers:
                    answer = input("(s/n) ").casefold()

                orcid_dict[orcid]['related_to_portuguese'] = answer in valid_yes_answers

    return orcid_dict

def load_author_portuguese_related(author_dict, orcid_dict=None, affiliation_dict=None):
    if orcid_dict is None:
        orcid_dict = load_dict(os.path.join('data', 'orcid.json'))
    if affiliation_dict is None:
        affiliation_dict = load_dict(os.path.join('data', 'affiliations.json'))
    if len(author_dict['affiliation']) > 0:
        for affiliation_raw in author_dict['affiliation']:
            affiliation_clean = clean_affiliation(affiliation_raw['name'])
            if load_affiliation_related_to_portuguese(affiliation_clean, affiliation_dict):
              author_dict['related_to_portuguese'] = True
    if 'ORCID' in author_dict:
        load_orcid(author_dict['ORCID'][-19:], orcid_dict, method='person')
        load_orcid(author_dict['ORCID'][-19:], orcid_dict, method='employments')
        load_orcid_related_to_portuguese(author_dict['ORCID'][-19:], orcid_dict)
        if 'related_to_portuguese' in orcid_dict[author_dict['ORCID'][-19:]]:
            author_dict['related_to_portuguese'] = author_dict.get('related_to_portuguese', False) or orcid_dict[author_dict['ORCID'][-19:]]['related_to_portuguese']


def load_doi_portuguese_affiliation(doi, doi_dict=None, orcid_dict=None, affiliation_dict=None):
    if doi_dict is None:
        doi_dict = load_dict(os.path.join('data', 'doi_metadata.json'))

    if doi not in doi_dict:
        load_agency_from_doi(new_doi, doi_dict)
        if doi_dict[new_doi]['agency'] == 'crossref':
            load_metadata_from_doi_crossref(new_doi, doi_dict)
        else:
            raise Error(f'doi {new_doi} não é do crossref, é do {doi_dict[new_doi]["agency"]}')
    
    if 'authors_related_to_portuguese' in doi_dict[doi]:
       #  ['authors_related_to_portuguese']
       return doi_dict

    unknown_authors = 0
    brazilian_authors = 0
    non_brazilian_authors = 0
    
    for author in doi_dict[doi]['metadata']['message']['author']:
        load_author_portuguese_related(author, orcid_dict, affiliation_dict)
        if 'related_to_portuguese' not in author:
            unknown_authors += 1
        elif author['related_to_portuguese']:
            brazilian_authors += 1
        else:
            non_brazilian_authors += 1
    
    if brazilian_authors > 0:
        doi_dict[doi]['authors_related_to_portuguese'] = True
    elif unknown_authors == 0 and non_brazilian_authors > 0 and brazilian_authors == 0:
        doi_dict[doi]['authors_related_to_portuguese'] = False

    return doi_dict


#Muzy
def add_meta(dataFrame, sbsi_dict, path):
    


    erro = 0

    for df in dataFrame.iterrows():

        if len(df[1]['doi'].strip()) < 5:
            try:
                response = requests.get('https://dblp.org/search/publ/api?q={0}&format=json'.format(df[1]['titulo']))
                response.raise_for_status()
                excel_doi = response.json()['result']['info']['ee']
                df[1]['doi'] = excel_doi
            except Exception as err:
                print('Erro ocorrido: {0}'.format(err))
                traceback.print_exc()
                continue

        for item in sbsi_dict:

            # encodes = []
            # encodes.append(item['info']['title'])
            # encodes.append(item['info']['title'].encode('utf-8').decode('unicode_escape'))
            # encodes.append(html.unescape(item['info']['title']))

            if item['info']['ee'] == df[1]['doi']:
                item['language'] = df[1]['idioma']
                break

            # for titulo_encode in encodes:
            #     if clean_affiliation(titulo_encode.rstrip(".")) == clean_affiliation(df[1]['titulo'].strip()):
            #         """if (item['language'] == '__label__en' and df[1]['idioma'] == 'pt-br' ) or (item['language'] == '__label__pt' and df[1]['idioma'] == 'en'):
            #             print (titulo_encode)
            #             erro+=1"""
            #         item['language'] = df[1]['idioma']
            #         break

                
            
    #print(erro)
    save_dict(sbsi_dict, path)
            
            

if __name__ == '__main__':
    """prepare_folders()

    publications_list = load_conference('sbsi')
    load_citators_from_publications(publications_list)

    orcid_json_path = os.path.join('data', 'orcid.json')
    orcid_dict = load_dict(orcid_json_path)

    affiliation_json_path = os.path.join('data', 'affiliations.json')
    affiliation_dict = load_dict(affiliation_json_path)

    doi_json_path = os.path.join('data', 'doi_metadata.json')
    doi_dict = load_dict(doi_json_path)

    for doi in [key for key in doi_dict.keys()]:
        print(doi)
        load_doi_portuguese_affiliation(doi, doi_dict, orcid_dict, affiliation_dict)
    
    save_dict(orcid_dict, orcid_json_path)
    save_dict(affiliation_dict, affiliation_json_path)
    save_dict(doi_dict, doi_json_path)"""


    #Muzy
    dataFrame = pd.read_excel('data/sbsi-metadata.xlsx')
    with open('conferences/sbsi.json') as f:
        sbsi_dict = json.load(f)
    add_meta(dataFrame, sbsi_dict,'conferences/sbsi_new.json')
    pd.save_excel('')


    # for publication in publications_list:
    #     if 'doi' not in publication['info']:
    #         print(publication)
    # authors = load_authors_from_publications(publications_list)
    # publications_list[:] = map(classify_publication_language_fasttext, publications_list)
    # save_conference_locally('sbsi', publications_list)
    # [print("{0} {1}: {2}".format(p['language'], publications_list.index(p), p['info']['title'])) for p in publications_list if p['language'] not in ['__label__pt', '__label__en']]

    # print(get_author_affiliations_dblp('o/JoniceOliveira'))
    

