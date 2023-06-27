import requests
import math
import json
import os
import fasttext
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
        
# def classify_publication_language_langid(publication):
#     language = langid.classify(publication['info']['title'])[0]
#     publication['language'] = language
#     return publication

def classify_publication_language_fasttext(publication):
    language = fasttext_model.predict(publication['info']['title'].split('[')[0], k=1)[0][0]
    publication['language'] = language
    return publication

def classify_publication_language(publication):
    return classify_publication_language_fasttext(publication)

def prepare_folders():
    os.makedirs('conferences', exist_ok = True)
    os.makedirs('authors', exist_ok = True)

if __name__ == '__main__':
    prepare_folders()
    publications_list = load_conference('sbsi')
    # publications_list[:] = map(classify_publication_language_fasttext, publications_list)
    # save_conference_locally('sbsi', publications_list)
    [print("{0} {1}: {2}".format(p['language'], publications_list.index(p), p['info']['title'])) for p in publications_list if p['language'] not in ['__label__pt', '__label__en']]

