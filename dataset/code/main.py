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
import json
from networks import CitationNet
import networkx as nx

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
                if paper_book_title == 'None': # if book_title not available check for journal name
                    paper_book_title = query_dict(fields_dict, 'journal')
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
        title_to_paper_details_fpath = './downloads/title_to_paper_filtered_details.csv'
        ref_paperids_fpath = './downloads/ref_paper_ids.csv'
        bib_paper_details_fpath = './downloads/bib_paper_details.csv'
        paper_country_fpath = './downloads/paper_country_list_all_company.json'
        country_citation_count_fpath = './downloads/country_cited_count.json'
        inter_country_citation_count_fpath = './downloads/inter_country_cited_count.json'
        inter_country_citation_count_wo_year_fpath = './downloads/inter_country_cited_count_wo_year.json'
        year_to_country_citation_count_fpath = './downloads/year_to_country_citation_count.json'
        country_to_country_referened_count_fpath = './downloads/country_to_referenced_country_counts.json'
        country_pair_to_clique_size_fpath = './downloads/country_pair_to_clique_size.json'
        country_pair_to_dominant_count_clique_size_fpath = './downloads/country_pair_to_dominant_count_clique_size.json'
        country_pair_to_dominant_fraction_clique_size_fpath = './downloads/country_pair_to_dominant_fraction_clique_size.json'
        regression_features_fpath = './downloads/paper_key_to_regression_features.csv'

        citenet = CitationNet(title_to_paper_details_fpath, ref_paperids_fpath, bib_paper_details_fpath, paper_country_fpath, 2021, bib_dict)
        # citenet.print_top_k_cited(20) # prints top-20 cited papers

        for i, paperID in enumerate(citenet.paper_features):
            if i >= 10:
                break
            paper_features = citenet.paper_features[paperID]
            print(paperID)
            print(paper_features)
    
        # output the features list in a csv
        row_header = ['paper-key', 'countries', 'author genders (in authorship order)', 'author names (in authorship order)', 'authors count', 'authors citations (uptil present; in authorship order)', 'authors citations (uptil year of publication; in authorship order)', 'nlp academic age (uptil present; in authorship order)', 'nlp academic age (uptil year of publication; in authorship order)', 'venue', 'min university rank', 'max university rank']
        with open(regression_features_fpath, 'w') as f:
            csv_writer = csv.writer(f, delimiter='|')
            csv_writer.writerow(row_header)
            paper_key_to_venue = json.load(open('./downloads/dict_paper_id_to_venue.json'))
            paper_key_to_min_rank_cat = json.load(open('./downloads/dict_paper_uni_minrank.json'))
            paper_key_to_mean_rank_cat = json.load(open('./downloads/dict_paper_uni_meanrank.json'))

            for i, paperID in enumerate(citenet.paper_features):

                paper_key = citenet.paper_features[paperID]['paper_key']
                paper_id_year = int(citenet.paper_features[paperID]['year'])

                # countries associated with the paper; excluding the company names
                countries = ','.join([country.strip() for country in citenet.paper_features[paperID]['countries'] if country not in citenet.company_names])
                if len(countries.strip()) == 0:
                    countries = 'unknown'

                # author count and names of authors
                authors = citenet.paper_features[paperID]['bib_authors']
                authors = ['~'.join([name.strip() for name in f_name_l_name]) for f_name_l_name in authors]
                authors_count = len(authors)
                authors = ','.join(authors)

                # gender of authors
                author_genders = citenet.paper_features[paperID]['bib_author_genders']
                author_genders = ','.join(author_genders)

                # citation uptil present & uptil year of publication | some papers might be missing in computation of citation count since few authors don't author ids from Semantic Scholar| len(author_names) - len(ciation_count) is missed authors for paper
                # unkonwn (without semnatic scholar id) authors are assinged 0 ciations
                citations_uptil_present, citations_uptil_yop = [], []
                author_ids = [auth_id_auth_name[0] for auth_id_auth_name in citenet.paper_features[paperID]['sem_authors'] if auth_id_auth_name!=['']] # what if author id doesn't take a valid value?
                for author_id in author_ids:
                    author_citation_count = citenet.cumulative_citations[author_id][paper_id_year]
                    citations_uptil_yop.append(author_citation_count)

                    final_year = max(citenet.cumulative_citations[author_id])
                    author_citation_count = citenet.cumulative_citations[author_id][final_year]
                    citations_uptil_present.append(author_citation_count)
                citations_uptil_yop = ','.join([str(count) for count in citations_uptil_yop])
                citations_uptil_present = ','.join([str(count) for count in citations_uptil_present])
                # empty string if citaitons not found for any of the authors
                
                # NLP academic age uptil present & uptil year of publication
                acad_age_uptil_present, acad_age_uptil_yop = [], []
                for author_id in author_ids:
                    acad_age_uptil_yop.append(paper_id_year - citenet.first_pub_year[author_id])
                    acad_age_uptil_present.append(final_year - citenet.first_pub_year[author_id])
                acad_age_uptil_yop = ','.join([str(age) for age in acad_age_uptil_yop])
                acad_age_uptil_present = ','.join([str(age) for age in acad_age_uptil_present])
                # empty string if citaitons not found for any of the authors

                # venue
                venue = paper_key_to_venue[paper_key]
                venue = 'unknown' if len(venue.strip())==0 else venue.strip()
                
                # min university rank
                if paper_key in paper_key_to_min_rank_cat:
                    min_rank = paper_key_to_min_rank_cat[paper_key]
                else:
                    min_rank = 'UNK'
                if min_rank is not None:
                    min_rank = min_rank.strip()
                else:
                    min_rank = 'UNK'
                min_rank = 'unknown' if min_rank is 'UNK' else min_rank
                
                # max university rank
                if paper_key in paper_key_to_mean_rank_cat:
                    mean_rank = paper_key_to_mean_rank_cat[paper_key]
                else:
                    mean_rank = 'UNK'
                if mean_rank is not None:
                    mean_rank = mean_rank.strip()
                else:
                    mean_rank = 'UNK'
                mean_rank = 'unknown' if mean_rank is 'UNK' else mean_rank

                row = [paper_key, countries, author_genders, authors, authors_count, citations_uptil_present, citations_uptil_yop, acad_age_uptil_present, acad_age_uptil_yop, venue, min_rank, mean_rank]
                csv_writer.writerow(row)

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
