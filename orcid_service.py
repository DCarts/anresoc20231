import requests
import orcid
import os
import json

if os.path.isfile('secret.json'):
    with open('secret.json', 'r') as input_file:
        secrets = json.load(input_file)

    
orcid_api = orcid.PublicAPI(secrets.get('orcid_client_id'), secrets.get('orcid_client_secret'), sandbox=False)
orcid_search_token = None
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

def load_orcid(orcid, orcid_dict=None, force=False, method='person'):
    global orcid_search_token
    if orcid_dict is None:
        orcid_dict = load_dict(os.path.join('data', 'orcid.json'))
    if orcid not in orcid_dict:
        orcid_dict[orcid] = {}
    if method not in orcid_dict[orcid] or force:
        if orcid_search_token is None:
            orcid_search_token = orcid_api.get_search_token_from_orcid()
        orcid_dict[orcid][method] = orcid_api.read_record_public(orcid, method, orcid_search_token)

    return orcid_dict

if __name__ == '__main__':
    orcid_search_token = orcid_api.get_search_token_from_orcid()
    print(json.dumps(orcid_api.read_record_public(input('orcid: '), input('metodo: '), orcid_search_token), indent=2))