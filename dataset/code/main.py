# Sample execution: python scripts/download_papers.py

import argparse
import requests
import sys
import os
import pickle
import random
import csv
import time
import urllib
from tqdm import tqdm
from pybtex.database.input import bibtex
from difflib import SequenceMatcher
from fuzzywuzzy import fuzz
from networks import CitationNet

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
                print(f"Multiple PDFs for {url_pdf} or {url_org} with {paper_key}!!!")
            pdf_found = True
    if not pdf_found:
        print(f"URL {url_pdf} or {url_org} for {paper_key} not found with pdf!!!")
    return pdf_found

def count_and_pause(request_count):
    request_count += 1
    if request_count == 99: # 100 requests per 1
        time.sleep(1)
        request_count = 0
    return request_count

def normalise_title(title):
    title_words = title.strip().split()
    is_alpha_num = lambda x: (ord('a') <= ord(x) and ord(x) <= ord('z')) or (ord('A') <= ord(x) and ord(x) <= ord('Z')) or (ord('0') <= ord(x) and ord(x) <= ord('9'))
    filter_word = lambda x: ''.join([char for char in x if is_alpha_num(char)])
    return ' '.join(' '.join([filter_word(word) for word in title_words]).split())
    
def fetch_paper_details(title, url, request_count):
    try:
        title_words = title.replace('{', '').replace('}', '').strip().split()

        # alternate (1) search string
        # is_alpha_num = lambda x: (ord('a') <= ord(x) and ord(x) <= ord('z')) or (ord('A') <= ord(x) and ord(x) <= ord('Z')) or (ord('0') <= ord(x) and ord(x) <= ord('9'))
        # filter_word = lambda x: ''.join([char for char in x if is_alpha_num(char)])
        # search_string_2 = '+'.join(' '.join([filter_word(word) for word in title_words]).split())

        # alternate (2) search string
        search_string = '-'.join(' '.join([word for word in title_words]).split())

        if 'doi.org' in url:
            doi_id = url[len('https://doi.org/'):]
            r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/DOI:{doi_id}?fields=authors,title', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
            request_count = count_and_pause(request_count)
            if r.status_code == 200:
                top_ret_paper = r
                request_type = 1
            else:
                r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/search?query={search_string}&fields=authors,title', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
                request_count = count_and_pause(request_count)
                top_ret_paper = r.json()['data'][0]   
                request_type = 2
        elif 'aclanthology.org' in url:
            acl_id = url[len('https://aclanthology.org/'):]
            r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/ACL:{acl_id}?fields=authors,title', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
            request_count = count_and_pause(request_count)
            if r.status_code == 200:
                top_ret_paper = r
                request_type = 1
            else:
                r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/search?query={search_string}&fields=authors,title', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
                request_count = count_and_pause(request_count)
                top_ret_paper = r.json()['data'][0]   
                request_type = 2
        else:
            r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/search?query={search_string}&fields=authors,title', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
            request_count = count_and_pause(request_count)
            top_ret_paper = r.json()['data'][0]
            request_type = 2

        print(f"Final request (type:{request_type}) output:", r.json())
        content_type = r.headers.get('content-type')

        if 'application/json' in content_type:
            if request_type == 1:
                top_ret_paper = r.json()
            else:
                top_ret_paper = r.json()['data'][0]
            paper_id, ret_title, authors = top_ret_paper['paperId'], top_ret_paper['title'], top_ret_paper['authors'] 
            authors_str = ""
            for author_and_id in authors:
                authorId, name = author_and_id['authorId'], author_and_id['name']
                authors_str = str(authors_str) + ('%' if len(authors_str)>0 else '') + str(authorId) + '#' + str(name)
            authors = [author_and_id.strip().split('#') for author_and_id in authors_str.strip().split('%')] # [[auth_1, auth_1_id], [auth_2, auth_2_id]]
        else:
            paper_id, ret_title, authors = 'None', 'None', []
            print(f'Paper details not found for: {title} | {url}')
        fuzzy_score = fuzz.ratio(normalise_title(ret_title), normalise_title(title))
    except:
        paper_id, ret_title, authors, request_type, fuzzy_score = 'None', 'None', [], -1, 0.0
        print(f'Paper details not found for: {title} | {url}')

    return paper_id, ret_title, authors, request_count, str(fuzzy_score), str(request_type)

def fetch_ref_paper_ids(paper_id, request_count):
    r = requests.get(f'https://api.semanticscholar.org/graph/v1/paper/{paper_id}/references', headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
    request_count = count_and_pause(request_count)
    content_type = r.headers.get('content-type')
    referenced_paper_ids = []
    if r.status_code == 200 and 'application/json' in content_type:
        ref_papers = r.json()['data']
        for paper in ref_papers:
            referenced_paper_ids.append(paper['citedPaper']['paperId'])
    else:
        print(f'References couldnt be fetched for paper id : {paper_id}.')

    referenced_paper_ids = [paper_id for paper_id in referenced_paper_ids if paper_id is not None] # filter None

    return referenced_paper_ids, request_count

def query_dict(dict_object, key):
    if key in dict_object:
        return dict_object[key]
    return 'None'

def main(args):
    bib_dict = read_bibfile(args.bib_path)
    bib_dict = {k: v for k, v in bib_dict.items() if v['type']!='proceedings'} # filter conference proceedings

    print("Sample bib-dict:")
    print(bib_dict[random.choice(list(bib_dict.keys()))])
    print("-"*50)

    if args.dump_bib_details: # ==> Dump details from bib file to csv format.
        with open('./downloads/bib_paper_details.csv', 'w') as csvfile:
            csvwriter = csv.writer(csvfile)
            csvwriter.writerow(['paper_key', 'paper_type', 'paper_title', 'paper_book_title', 'month', 'year', 'url'])
            for paper_key in tqdm(bib_dict):
                paper_type = bib_dict[paper_key]['type']
                fields_dict = bib_dict[paper_key]['fields']
                paper_title, paper_book_title, paper_month, paper_year, paper_url = fields_dict['title'], query_dict(fields_dict, 'booktitle'), query_dict(fields_dict, 'month'), query_dict(fields_dict, 'year'), query_dict(fields_dict, 'url')
                csvwriter.writerow([paper_key, paper_type, paper_title, paper_book_title, paper_month, paper_year, paper_url])
                        
    if args.download_pdfs: # ==> Download pdfs from ACL anthology.
        create_folder('./downloads/pdfs')
        for paper_key in tqdm(bib_dict):
            download_pdf(bib_dict[paper_key]['fields']['url'], paper_key)
    
    if args.fetch_paper_details: # ==> Fetch paper-ids and references corresponding to each paper.
        ss_request_counts = 0
        correct_paper_details, total_paper_details = 0.0, 0.0

        # 1. create a [title -> paper_id, [author, author_id]] mapping
        title_to_paper_details_filepath = './downloads/title_to_paper_details.csv'
        title_to_paper_details = dict()

        if os.path.exists(title_to_paper_details_filepath): # reading existing mappings
            with open(title_to_paper_details_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    print('row:', row)
                    paper_id, bib_title, ret_title, authors, fuzzy_score, request_type = row 
                    authors = [author_and_id.strip().split('#') for author_and_id in authors.strip().split('%')] # auth_1#auth_1_id%auth_2#auth_2_id
                    title_to_paper_details[bib_title] = [paper_id, ret_title, authors, fuzzy_score, request_type]
                    if (request_type=="1") or (request_type=="2" and fuzzy_score=="100"):
                        correct_paper_details += 1
                    total_paper_details += 1

        with open(title_to_paper_details_filepath, 'a') as csvfile:
            csvwriter = csv.writer(csvfile)

            for paper_key in tqdm(bib_dict):
                bib_title = bib_dict[paper_key]['fields']['title']
                if bib_title not in title_to_paper_details:
                    url = bib_dict[paper_key]['fields']['url']
                    paper_id, ret_title, authors, ss_request_counts, fuzzy_score, request_type = fetch_paper_details(bib_title, url, ss_request_counts)
                    title_to_paper_details[bib_title] = [paper_id, ret_title, authors, fuzzy_score, request_type]

                    # append new entries
                    authors_str = '%'.join(['#'.join(author_and_id) for author_and_id in authors])
                    row = [paper_id, bib_title, ret_title, authors_str, fuzzy_score, request_type]
                    csvwriter.writerow(row)

                    if (request_type=="1") or (request_type=="2" and fuzzy_score=="100"):
                        correct_paper_details += 1
                    total_paper_details += 1

                print("Current Correct Paper Details Fraction:", 100.0*correct_paper_details/total_paper_details)
        
        print("Total papers querid:", len(title_to_paper_details))

        # 2. create a [paper_id -> [list of referenced paper_ids]] mapping
        ref_paperids_filepath = './downloads/ref_paper_ids.csv'
        ref_paperids = dict()

        if os.path.exists(ref_paperids_filepath): # reading existing mappings
            with open(ref_paperids_filepath) as f:
                for line in f:
                    split_line = line.strip().split(',')
                    paper_id, referenced_paper_ids = split_line[0], split_line[1:]
                    if referenced_paper_ids[0] == '' and len(referenced_paper_ids) == 1:
                        referenced_paper_ids = []
                    ref_paperids[paper_id] = referenced_paper_ids
        
        with open(ref_paperids_filepath, 'a') as f:
            for paper_key in tqdm(bib_dict):
                bib_title = bib_dict[paper_key]['fields']['title']
                paper_id = title_to_paper_details[bib_title][0]
                if paper_id != 'None' and paper_id not in ref_paperids:
                    ref_paperids[paper_id], ss_request_counts = fetch_ref_paper_ids(paper_id, ss_request_counts)
                    f.write(f'{paper_id},{",".join(ref_paperids[paper_id])}\n')
    
    if args.clean_paper_details: # ==> Manually clean up partially correct paper details.
        title_to_paper_details_filepath = './downloads/title_to_paper_details.csv'
        title_to_filtered_paper_details_filepath = './downloads/title_to_paper_filtered_details.csv'
        paper_details, filtered_paper_details = [], []

        if os.path.exists(title_to_paper_details_filepath): # reading the mappings
            with open(title_to_paper_details_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    paper_details.append(row) # row = [paper_id, bib_title, ret_title, authors, fuzzy_score, request_type]

        def order_index(paper_row):
            if paper_row[-1] == "1":
                return -101
            elif paper_row[-1] == "2":
                return -int(paper_row[-2])
            else:
                return 1

        paper_details = sorted(paper_details, key=order_index)

        def do_titles_match(bib_title, ret_title, fuzzy_score):
            print("Do these match?")
            print("Fuzzy Score:", fuzzy_score)
            print(ret_title, "- semantic scholar title") 
            print(bib_title, "- bib title")
            input_string = input()
            while input_string not in ['y', 'n', 'Y', 'n']:
                input_string = input()
            if input_string in ['y', 'Y']:
                return True
            return False

        filtered_paper_count = 0
        for row in tqdm(paper_details):
            if row[-1] == "-1":
                filtered_paper_count += 1 # exclude
            elif row[-1] == "2":
                if int(row[-2]) < 85:
                    if do_titles_match(row[1], row[2], row[-2]):
                        filtered_paper_details.append(row)
                    else:
                        filtered_paper_count += 1 # exclude
                else:
                    filtered_paper_details.append(row)
            else:
                filtered_paper_details.append(row) 
        print("Papers excluded in filtering:", filtered_paper_count)

        with open(title_to_filtered_paper_details_filepath, 'w') as csvfile:
            csvwriter = csv.writer(csvfile)
            for row in filtered_paper_details:
                csvwriter.writerow(row)

    if args.create_cite_net: # create the acl citation network.
        title_to_paper_details_filepath = './downloads/title_to_paper_filtered_details.csv'
        ref_paperids_filepath = './downloads/ref_paper_ids.csv'
        citenet = CitationNet(title_to_paper_details_filepath, ref_paperids_filepath)
        citenet.print_top_k_cited(20)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--bib_path", default='./downloads/anthology+abstracts.bib', type=str, 
                        help='path to file with all the bibtex')
    parser.add_argument("--dump_bib_details", action='store_true', default=False, 
                        help='dumps some details from the bibtex file')
    parser.add_argument("--download_pdfs", action='store_true', default=False, 
                        help='if true, download and save pdfs')
    parser.add_argument("--fetch_paper_details", action='store_true', default=False, 
                        help='if true, use semantic scholar APIs to fetch relevant paper details')
    parser.add_argument("--clean_paper_details", action='store_true', default=False, 
                        help='cleans the title_to_paper_details csv file.')
    parser.add_argument("--create_cite_net", action='store_true', default=False, 
                        help='creates citation network using the fetched paper details.')
    args = parser.parse_args()
    
    main(args)