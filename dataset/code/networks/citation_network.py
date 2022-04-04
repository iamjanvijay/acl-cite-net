import csv
import os
import json
import re
import statistics
from tqdm import tqdm

class CitationNet:
    def __init__(self, paper_details_filepath, references_filepath, bib_details_filepath, country_list_filepath, thresold_year, verbose=True):
        self.paper_to_references = dict() # paperID => [list of references of paper with paperID]
        self.paper_to_citedby = dict() # paperID => [list of papers citing paper with paperID]
        self.paper_features = dict() # paperID => [dictonary of features of paper with paperID]
        self.cache = dict() # stores some results to speed-up computations
        self.company_names = ['google', 'amazon', 'facebook', 'microsoft', 'huggingface', 'ibm', 'bloomberg', 'yahoo', 'samsung', 'alibaba', 'allenai', 'baidu']

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
                if verbose:
                    print(f"** Country list not found for paper {paper_key}.")
                missing += 1
            total += 1
            self.paper_features[paper_id]['countries'] = list(set(country_list)) # unique

        print(f"*** Total {missing} out of {total} paper-keys missing in country list.")
    
    def country_to_publications(self):
        '''
            Return the dict with paper_ids corresponding to each country.
            country_name => [paper_id_1, paper_id_2 ... paper_id_n]
            paper_id_1, paper_id_2 ... paper_id_n are n papers associated with country_name
        '''
        country_to_paper_ids = dict()
        for paper_id in self.paper_features:
            country_list = self.paper_features[paper_id]['countries']
            for country in country_list:
                if country not in country_to_paper_ids:
                    country_to_paper_ids[country] = []
                country_to_paper_ids[country].append(paper_id)
        return country_to_paper_ids

    def extract_country_cited_count(self, save_fpath):
        '''
            for every "paper" (say X) identies the "count of papers" (Y) citing it;
            identifies countries associated with X and returns an aggregated list of form: 
            "country" (associated with "paper" X_1, X_2, ... X_n) => [Y_1, Y_2, ... Y_n]
        '''
        country_cited_count = dict()
        for paper_id in self.paper_to_citedby:
            citations = len(self.paper_to_citedby[paper_id])
            country_list = self.paper_features[paper_id]['countries']
            for country in country_list:
                if country not in country_cited_count:
                    country_cited_count[country] = []
                country_cited_count[country].append(citations)
        
        if save_fpath==None:
            return country_cited_count

        for country in country_cited_count:
            print(f"Country: {country}")
            print("-"*50)
            mean_citation = statistics.mean(country_cited_count[country])
            median_citation = statistics.median(country_cited_count[country])
            print(f"Mean: {mean_citation} | Median: {median_citation} | Support: {len(country_cited_count[country])}")
            print("-"*50)
        
        with open(save_fpath, 'w') as f:
            json.dump(country_cited_count, f)

    def paper_1_cites_paper_2(self, paper_1_id, paper_2_id):
        '''
        Returns True if paper with paper_id_1 cites paper with paper_id_2; else returns False.
        '''
        if 'paper_1_cites_paper_2' not in self.cache:
            self.cache['paper_1_cites_paper_2'] = dict()
            for paper_1_id in self.paper_to_references:
                for paper_2_id in self.paper_to_references[paper_1_id]:
                    self.cache['paper_1_cites_paper_2'][(paper_1_id, paper_2_id)] = True # paper_1_id cites paper_2_id
            print("paper_1_cites_paper_2 cache created...")

        return (paper_1_id, paper_2_id) in self.cache['paper_1_cites_paper_2']

    def paper_1_could_cite_paper_2(self, paper_1_id, paper_2_id):
        '''
        Returns True if paper with paper_id_1 could have cited paper with paper_id_2; else returns False.
        '''
        return (int(self.paper_features[paper_1_id]['year']) >= int(self.paper_features[paper_2_id]['year']))

    def extract_cross_country_cited_count(self, save_fpath, k):
        '''
            selects top_k countries by total publication count;
            computes number of times country 'x' is cited by country 'y';
            also averages the last metric over total papers of x and total papers of y.
        '''

        country_to_paper_ids = self.country_to_publications()
        country_to_paper_ids = {k: country_to_paper_ids[k] for k in country_to_paper_ids if k not in self.company_names} # filter out company names
        top_k_countries = sorted(country_to_paper_ids.items(), key=lambda x: -len(x[1]))[:k]
        country_1_cites_country_2_stats = dict()

        for country_1, country_1_paper_ids in top_k_countries:
            for country_2, country_2_paper_ids in top_k_countries:
                country_1_cites_country_2_stats[f"{country_1}#{country_2}"] = {
                                                                            'citation_count': 0, 
                                                                            'possible_citations_w_year': 0,
                                                                            'possible_citations_wo_year': 0
                                                                        }
                print(f"Computing stats for {country_1} [num-papers: {len(country_1_paper_ids)}] citing {country_2} [num-papers: {len(country_2_paper_ids)}]...")
                # compute stats for country_1 cites country_2
                for paper_id_1 in tqdm(country_1_paper_ids):
                    for paper_id_2 in country_2_paper_ids:
                        if paper_id_1==paper_id_2: # a common paper
                            continue

                        if self.paper_1_cites_paper_2(paper_id_1, paper_id_2):
                            country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['citation_count'] += 1

                        if self.paper_1_could_cite_paper_2(paper_id_1, paper_id_2):
                            country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['possible_citations_w_year'] += 1
                        country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['possible_citations_wo_year'] += 1

                country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['citation_density_w_year'] = float(country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['citation_count']) / country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['possible_citations_w_year']
                country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['citation_density_wo_year'] = float(country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['citation_count']) / country_1_cites_country_2_stats[f"{country_1}#{country_2}"]['possible_citations_wo_year']

        with open(save_fpath, 'w') as f:
            json.dump(country_1_cites_country_2_stats, f)

    # methods just to print some stats.

    def same_year_citations_fraction(self):
        total_citations, same_year_citations, future_year_citations = 0., 0., 0.
        for paper_id in self.paper_to_references:
            total_citations += len(self.paper_to_references[paper_id])
            for cited_paper_id in self.paper_to_references[paper_id]:
                if int(self.paper_features[cited_paper_id]['year']) > int(self.paper_features[paper_id]['year']):
                    future_year_citations += 1
                if int(self.paper_features[cited_paper_id]['year']) == int(self.paper_features[paper_id]['year']):
                    same_year_citations += 1
        print(f"total citations: {total_citations} | same_year_citations: {same_year_citations} | fraction of same year citations: {100 * same_year_citations / total_citations}")
        print(f"total citations: {total_citations} | future_year_citations: {future_year_citations} | fraction of future year citations: {100 * future_year_citations / total_citations}")

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



