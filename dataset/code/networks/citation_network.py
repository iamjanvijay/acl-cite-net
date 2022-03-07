import csv
import os
import json
import re
import statistics

class CitationNet:
    def __init__(self, paper_details_filepath, references_filepath, bib_details_filepath, country_list_filepath, thresold_year):
        self.paper_to_references = dict() # paperID => [list of references of paper with paperID]
        self.paper_to_citedby = dict() # paperID => [list of papers citing paper with paperID]
        self.paper_features = dict() # paperID => [dictonary of features of paper with paperID]

        with open(bib_details_filepath) as csvfile: # load bib details.
            bib_title_to_bib_details = dict()
            csvreader = csv.reader(csvfile)
            for i, row in enumerate(csvreader):
                if i==0:
                    continue
                paper_key, paper_type, paper_title, paper_book_title, month, year, url = row
                bib_title_to_bib_details[paper_title] = [paper_key, paper_type, paper_book_title, month, year, url]

        def is_valid_paper_id(bib_title, bib_title_to_bib_details, thresold_year):
            if int(bib_title_to_bib_details[bib_title][4]) <= thresold_year:
                return True
            return False

        if os.path.exists(paper_details_filepath): # Read the details of all the papers and create nodes.
            with open(paper_details_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    paper_id, bib_title, ret_title, authors, fuzzy_score, request_type = row 
                    if is_valid_paper_id(bib_title, bib_title_to_bib_details, thresold_year):
                        authors = [author_and_id.strip().split('#') for author_and_id in authors.strip().split('%')] # [[auth_1, auth_1_id], [auth_2, auth_2_id]]
                        self.paper_to_references[paper_id] = set()
                        self.paper_features[paper_id] = {'bib_title': bib_title, 'sem_title': ret_title, 'authors': authors}

        if os.path.exists(references_filepath): # read referenced papers and add citation edges.
            with open(references_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    curr_paper_id, cited_paper_ids = row[0], row[1:]
                    if curr_paper_id in self.paper_to_references:
                        self.paper_to_references[curr_paper_id] = self.paper_to_references[curr_paper_id] | set([id for id in cited_paper_ids if id in self.paper_to_references]) # only those paper ids which are in ACL network
                        for referenced_paper_id in self.paper_to_references[curr_paper_id]:
                            if referenced_paper_id not in self.paper_to_citedby:
                                self.paper_to_citedby[referenced_paper_id] = set()
                            self.paper_to_citedby[referenced_paper_id].add(curr_paper_id)

        print("finished creating citation network...")

        with open(country_list_filepath) as f: # load country annotations.
            paper_key_to_country_list = json.load(f)

        missing, total = 0, 0
        for paper_id in self.paper_features: # adding bib-details and country annotations in nodes.
            paper_key, paper_type, paper_book_title, month, year, url = bib_title_to_bib_details[self.paper_features[paper_id]['bib_title']] 
            self.paper_features[paper_id]['paper_key'] = paper_key
            self.paper_features[paper_id]['paper_type'] = paper_type
            self.paper_features[paper_id]['paper_book_title'] = paper_book_title
            self.paper_features[paper_id]['month'] = month
            self.paper_features[paper_id]['year'] = year

            key_for_country_list = paper_key + '.txt'
            if key_for_country_list in paper_key_to_country_list:
                country_list = paper_key_to_country_list[key_for_country_list]
            else:
                country_list = []
                print(f"** Country list not found for paper {paper_key}.")
                missing += 1
            total += 1
            self.paper_features[paper_id]['countries'] = list(set(country_list)) # unique

        print(f"*** Total {missing} out of {total} paper-keys missing in country list.")

    def print_top_k_cited(self, k):
        top_k_papers = sorted(self.paper_to_citedby.items(), key=lambda x: -len(x[1]))[:k]
        print("-"*50)  
        print("TOP CITED PAPERS:")
        print("-"*50) 
        for i, (paper_id, cited_by) in enumerate(top_k_papers):
            print(f"Paper #{i+1}:")
            print(f"TITLE: {self.paper_features[paper_id]['sem_title']}")
            print(f"Cited by {len(cited_by)} papers.")
            print("-"*50)

    def extract_country_cited_count(self, save_fpath):
        country_cited_count = dict()
        for paper_id in self.paper_to_citedby:
            citations = len(self.paper_to_citedby[paper_id])
            country_list = self.paper_features[paper_id]['countries']
            for country in country_list:
                if country not in country_cited_count:
                    country_cited_count[country] = []
                country_cited_count[country].append(citations)
        
        for country in country_cited_count:
            print(f"Country: {country}")
            print("-"*50)
            mean_citation = statistics.mean(country_cited_count[country])
            median_citation = statistics.median(country_cited_count[country])
            print(f"Mean: {mean_citation} | Median: {median_citation} | Support: {len(country_cited_count[country])}")
            print("-"*50)
        
        with open(save_fpath, 'w') as f:
            json.dump(country_cited_count, f)





