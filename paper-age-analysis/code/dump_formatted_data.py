import os
import sys
import csv
import requests
import json
import concurrent.futures
from tqdm import tqdm
import shutil

# input files
bib_details_file = '../dataset/downloads/bib_paper_details.csv'
title_to_filtered_details = '../dataset/downloads/title_to_paper_filtered_details.csv'
old_references_details = '../dataset/downloads/ref_paper_ids.csv'

# output files
references_file = './data/s2_paper_keys_for_references.csv'
paper_details_file = './data/s2_paper_keys_to_paper_details.json'

# cache file
request_to_response_file = './cache/request_to_response.csv' # dump the request_url and response_file_json for successful requests
requests_cache = './cache'
os.makedirs(requests_cache, exist_ok = True)

# sent a request
def request_to_respose(request_url):
    request_response = requests.get(request_url, headers={'x-api-key': 'qZWKkOKyzP5g9fgjyMmBt1MN2NTC6aT61UklAiyw'})
    return request_response

# cache folder to save json output of request
cur_request_id = 0
cached_request_response = dict()
if os.path.exists(request_to_response_file):
    with open(request_to_response_file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=',')
        for line_idx, row in enumerate(csv_reader):
            request_url, request_id = row
            # incrementing number of successfull requests
            cur_request_id = int(request_id) + 1
            # aggregating cached request responses in the cache dict
            with open(os.path.join(requests_cache, f'{request_id}.json'), "r") as infile:
                response_json = json.load(infile)
                cached_request_response[request_url] = response_json

def save_response_to_cache(request_url, response_json):
    global cur_request_id
    with open(request_to_response_file, 'a') as csv_file:
        writer = csv.writer(csv_file)
        # make a entry in mapping file
        writer.writerow([request_url, cur_request_id])
        # save the response json file
        with open(os.path.join(requests_cache, f'{cur_request_id}.json'), 'w') as f_json:
            json.dump(response_json, f_json)
        # updating cache dict
        cached_request_response[request_url] = response_json
        # incrementing number of successfull requests
        cur_request_id += 1

def response_from_cache(request_url):
    # return response from cache dict if available otherwise return -1
    global cached_request_response
    if request_url in cached_request_response:
        return cached_request_response[request_url]
    return -1

# loading paper detail from bib
count = 0
paper_title_to_details = dict()
with open(bib_details_file) as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    for line_idx, row in enumerate(csv_reader):
        if line_idx == 0:
            continue
        acl_paper_key, paper_type, paper_title, paper_book_title, month, year, url = row
        if paper_title not in paper_title_to_details: # first entry for this paper title
            paper_title_to_details[paper_title] = [[acl_paper_key, paper_type, paper_book_title, month, year, url],] 
        else: # additional entries for this paper title
            paper_title_to_details[paper_title].append([acl_paper_key, paper_type, paper_book_title, month, year, url]) 
        count += 1

print("Fetching paper-details for acl papers...")
missed_count, total_count = 0, 0
paper_details = dict() # each entry has s2_paper_key => [bib_tile, acl_paper_key, paper_type, paper_book_title, month, year, url, authors]
with open(title_to_filtered_details) as csv_file:
    csv_reader = csv.reader(csv_file, delimiter=',')
    for line_idx, row in enumerate(tqdm(list(csv_reader))):
        s2_paper_key, bib_title, s2_title, authors, fuzzy_score, request_type = row
        authors = [author_and_id.strip().split('#') for author_and_id in authors.strip().split('%')]
        if bib_title not in paper_title_to_details:
            continue
        if len(paper_title_to_details[bib_title]) > 1: # if bib has multilple entries for this paper title with multiple veuneus
            updated_cur_rows = []
            for cur_row in paper_title_to_details[bib_title]:
                acl_id = cur_row[-1][len('https://aclanthology.org/'):] # acl-url to acl-id
                request_url = f'https://api.semanticscholar.org/graph/v1/paper/ACL:{acl_id}?fields=authors'

                response_json = response_from_cache(request_url) # check in cache
                if response_json != -1: # if found in cache
                    # do work
                    s2_paper_key, authors = response_json['paperId'], response_json['authors']
                    authors = [[author['authorId'], author['name']] for author in authors]
                    updated_cur_rows.append([s2_paper_key,] + cur_row + [authors,])
                    paper_details[s2_paper_key] = dict(zip(['title', 'acl_paper_key', 'paper_type', 'venue', 'month', 'year', 'url', 'authors'], [bib_title,] + cur_row + [authors,]))
                    paper_details[s2_paper_key]['acl'] = True
                else: # if not found in cache
                    r = request_to_respose(request_url)
                    if r.status_code == 200: # if successful request
                        # save the request response json in cache
                        save_response_to_cache(request_url, r.json())
                        # do work
                        s2_paper_key, authors = r.json()['paperId'], r.json()['authors']
                        authors = [[author['authorId'], author['name']] for author in authors]
                        updated_cur_rows.append([s2_paper_key,] + cur_row + [authors,])
                        paper_details[s2_paper_key] = dict(zip(['title', 'acl_paper_key', 'paper_type', 'venue', 'month', 'year', 'url', 'authors'], [bib_title,] + cur_row + [authors,]))
                        paper_details[s2_paper_key]['acl'] = True
                    else:
                        missed_count += 1

                total_count += 1
            paper_title_to_details[bib_title] = updated_cur_rows # updating paper_title_to_details with s2_paper_key and authors
        else:
            paper_details[s2_paper_key] = dict(zip(['title', 'acl_paper_key', 'paper_type', 'venue', 'month', 'year', 'url', 'authors'], [bib_title,] + paper_title_to_details[bib_title][0] + [authors,]))
            paper_details[s2_paper_key]['acl'] = True
            paper_title_to_details[bib_title] = [[s2_paper_key,] + paper_title_to_details[bib_title][0] + [authors,]] # updating paper_title_to_details with s2_paper_key and authors
            total_count += 1

print(f"{missed_count} missed entires with multiple publications for same title, among a total paper count of {total_count}")

USE_OLD_REF_DETAILS = False
if USE_OLD_REF_DETAILS:
    with open(paper_details_file, 'w') as f_json:
        json.dump(paper_details, f_json)
    shutil.copy(old_references_details, references_file)
    exit()

# identifying the references and dumping them out
print("Fetching refereces for acl papers...")
total_references, none_references = 0, 0
non_acl_s2_paper_keys = set() # s2_paper_keys corresponding to non *CL papers
failed_requests = 0
futures = []
with open(references_file, 'w') as fw:
    with concurrent.futures.ThreadPoolExecutor(max_workers = 50) as executor:
        # check in cache dict otherwise send a requests in multiple-threads
        for s2_paper_key in paper_details:
            request_url = f'https://api.semanticscholar.org/graph/v1/paper/{s2_paper_key}?fields=references'
            response_json = response_from_cache(request_url) # check in cache
            if response_json == -1: # if reponse to request url not already in cache
                futures.append(executor.submit(request_to_respose, request_url))
            else: # if reponse to request url already in cache
                # do work
                s2_paper_key = response_json['paperId']
                if 'references' not in response_json:
                    continue
                s2_ref_paper_keys = [reference_paper_tuple['paperId'] for reference_paper_tuple in response_json['references']]
                filtered_s2_ref_paper_keys = [s2_ref_paper_key for s2_ref_paper_key in s2_ref_paper_keys if s2_ref_paper_key is not None]
                total_references += len(s2_ref_paper_keys)
                none_references += (len(s2_ref_paper_keys) - len(filtered_s2_ref_paper_keys))
                s2_ref_paper_keys = filtered_s2_ref_paper_keys
                out_str = ','.join([s2_paper_key,] + s2_ref_paper_keys) + '\n' # first paper_key is for the new paper and rest of the paper_keys are for referenced papers
                fw.write(out_str)

                # accumulate the s2_paper_keys for non *CL references
                for s2_ref_paper_key in s2_ref_paper_keys:
                    if s2_ref_paper_key not in paper_details:
                        non_acl_s2_paper_keys.add(s2_ref_paper_key)

        # using the responses from the sent requests
        for task in tqdm(concurrent.futures.as_completed(futures), total=len(futures), leave=True):
            r = task.result()
            if r.status_code == 200: # if sucessful request
                # save the request response json in cache
                s2_paper_key = r.json()['paperId']
                request_url = f'https://api.semanticscholar.org/graph/v1/paper/{s2_paper_key}?fields=references'
                save_response_to_cache(request_url, r.json())
                # do work
                if 'references' not in r.json():
                    continue
                s2_ref_paper_keys = [reference_paper_tuple['paperId'] for reference_paper_tuple in r.json()['references']]
                filtered_s2_ref_paper_keys = [s2_ref_paper_key for s2_ref_paper_key in s2_ref_paper_keys if s2_ref_paper_key is not None]
                total_references += len(s2_ref_paper_keys)
                none_references += (len(s2_ref_paper_keys) - len(filtered_s2_ref_paper_keys))
                s2_ref_paper_keys = filtered_s2_ref_paper_keys
                out_str = ','.join([s2_paper_key,] + s2_ref_paper_keys) + '\n' # first paper_key is for the new paper and rest of the paper_keys are for referenced papers
                fw.write(out_str)

                # accumulate the s2_paper_keys for non *CL references
                for s2_ref_paper_key in s2_ref_paper_keys:
                    if s2_ref_paper_key not in paper_details:
                        non_acl_s2_paper_keys.add(s2_ref_paper_key)
            else:
                failed_requests += 1 
print(f"{none_references} refereces were there for which 'None' s2-paper-keys were reteived among a total of {total_references} references")
print(f"Total failed request for computing references: {failed_requests} out of {len(futures)}")

# append details for non-acl papers in paper_detail
print("Fetching paper-details for non-acl papers...")
futures = []
failed_requests = 0
with concurrent.futures.ThreadPoolExecutor(max_workers = 50) as executor:
    # multi-threaded fetching...
    for s2_paper_key in non_acl_s2_paper_keys:
        request_url = f'https://api.semanticscholar.org/graph/v1/paper/{s2_paper_key}?fields=venue,year,title'
        response_json = response_from_cache(request_url) # check in cache
        if response_json == -1: # if reponse to request url not already in cache
            futures.append(executor.submit(request_to_respose, request_url))
        else: # if reponse to request url already in cache
            # do work
            s2_paper_key, title, venue, year = response_json['paperId'], response_json['title'], response_json['venue'], response_json['year']
            paper_details[s2_paper_key] = {'title':title, 'venue': venue, 'year': str(year), 'acl': False}

    # using the responses from the sent requests
    for task in tqdm(concurrent.futures.as_completed(futures), total=len(futures), leave=True):
        # Check the status of the task
        if task.done():
            r = task.result()
            if r.status_code == 200: # if sucessful request
                s2_paper_key, title, venue, year = r.json()['paperId'], r.json()['title'], r.json()['venue'], r.json()['year']
                request_url = f'https://api.semanticscholar.org/graph/v1/paper/{s2_paper_key}?fields=venue,year,title'
                save_response_to_cache(request_url, r.json())
                paper_details[s2_paper_key] = {'title':title, 'venue': venue, 'year': str(year), 'acl': False}
            else:
                failed_requests += 1 

print(f"Total failed request for computing paper details of non-acl papers: {failed_requests} out of {len(futures)}")
with open(paper_details_file, 'w') as f_json:
    json.dump(paper_details, f_json)

    




