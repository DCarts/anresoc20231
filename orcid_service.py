import requests
import orcid
import os
import json

if os.path.isfile('secret.json'):
    with open('secret.json', 'r') as input_file:
        secrets = json.load(input_file)

    
orcid_api = orcid.PublicAPI(secrets.get('orcid_client_id'), secrets.get('orcid_client_secret'), sandbox=False)
orcid_search_token = orcid_api.get_search_token_from_orcid()

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

def load_orcid(orcid, orcid_dict=None, force=False):
    if orcid_dict is None:
        orcid_dict = load_dict(os.path.join('data', 'orcid.json'))
    if orcid not in orcid_dict or force:
        orcid_dict[orcid] = orcid_api.read_record_public(orcid, 'person', orcid_search_token)
    return orcid_dict