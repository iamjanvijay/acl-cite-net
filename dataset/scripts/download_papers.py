# Sample execution: python scripts/download_papers.py

import argparse
import requests
import sys
import os
import pickle
import random
from tqdm import tqdm
from pybtex.database.input import bibtex

def read_bibfile(filepath):
    if filepath=='./downloads/anthology+abstracts.bib' and os.path.exists('./downloads/anthology+abstracts.pkl'):
        with open('./downloads/anthology+abstracts.pkl', 'rb') as handle:
            bib_dict = pickle.load(handle)
        return bib_dict

    parser = bibtex.Parser()
    bib_data = parser.parse_file(filepath)

    bib_dict = dict()
    for paper_key in bib_data.entries.keys():
        bib_dict[paper_key] = dict()
        bib_dict[paper_key]['fields'] = dict(bib_data.entries[paper_key].fields)
        bib_dict[paper_key]['type'] = bib_data.entries[paper_key].type
        authors_list = list(dict(bib_data.entries[paper_key].persons).values())
        assert(len(authors_list) <= 1) 
        if len(authors_list) == 0:
            bib_dict[paper_key]['authors'] = []
        else:
            bib_dict[paper_key]['authors'] = [(' '.join(person.get_part('first')), ' '.join(person.get_part('last'))) for person in authors_list[0]]

    if filepath=='./downloads/anthology+abstracts.bib':
        with open('./downloads/anthology+abstracts.pkl', 'wb') as handle:
            pickle.dump(bib_dict, handle, protocol=pickle.HIGHEST_PROTOCOL)
    
    return bib_dict

def create_folder(folder_path):
    if not os.path.exists(folder_path):
        os.makedirs(folder_path)

def download_pdf(url_org, paper_key):
    url_pdf = url_org + '.pdf'
    filepath = os.path.join('./downloads/pdfs', paper_key + '.pdf')

    if os.path.exists(filepath): # already downloaded
        return True 

    pdf_found = False
    for url in [url_pdf, url_org]:
        r = requests.get(url, allow_redirects=True)
        content_type = r.headers.get('content-type')
        if r.status_code == 200 and 'application/pdf' in content_type: # url exits and pdf file
            with open(filepath, 'wb') as f:
                f.write(r.content)
            if pdf_found:
                print("Multiple PDFs for {url_pdf} or {url_org} with {paper_key}!!!")
            pdf_found = True
    if not pdf_found:
        print(f"URL {url_pdf} or {url_org} for {paper_key} not found with pdf!!!")
    return pdf_found
    


def main(args):
    bib_dict = read_bibfile(args.bib_path)
    print("Sample bib-dict:")
    print(bib_dict[random.choice(list(bib_dict.keys()))])
    print("-"*50)

    bib_dict = {k: v for k, v in bib_dict.items() if v['type']!='proceedings'} # filter conference proceedings

    create_folder('./downloads/pdfs')
    for paper_key in tqdm(bib_dict):
        download_pdf(bib_dict[paper_key]['fields']['url'], paper_key)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--bib_path", default='./downloads/anthology+abstracts.bib', type=str, 
                        help='path to file with all the bibtex')
    args = parser.parse_args()
    
    main(args)