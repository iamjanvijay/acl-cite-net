import csv
import os
import json
import re
import statistics
from tqdm import tqdm

def strip_non_alpha(text):
    return ''.join([i for i in text if i.isalpha()])

class CitationNet:
    def __init__(self, paper_details_filepath, references_filepath, bib_details_filepath, country_list_filepath, thresold_year, bib_dict, verbose=True):
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
                bib_title_to_bib_details[paper_title].append(bib_dict[paper_key]['authors']) # (first, last) sorted in authorship order

        def is_valid_paper_id(bib_title, bib_title_to_bib_details, thresold_year):
            if int(bib_title_to_bib_details[bib_title][4]) <= thresold_year:
                return True
            return False

        if os.path.exists(paper_details_filepath): # Read the details of all the papers and create nodes.
            with open(paper_details_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    paper_id, bib_title, ret_title, sem_authors, fuzzy_score, request_type = row 
                    if is_valid_paper_id(bib_title, bib_title_to_bib_details, thresold_year):
                        sem_authors = [author_and_id.strip().split('#') for author_and_id in sem_authors.strip().split('%')] # [[auth_1, auth_1_id], [auth_2, auth_2_id]]
                        self.paper_to_references[paper_id] = set()
                        self.paper_features[paper_id] = {'bib_title': bib_title, 'sem_title': ret_title, 'sem_authors': sem_authors}

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
            paper_key, paper_type, paper_book_title, month, year, url, bib_authors = bib_title_to_bib_details[self.paper_features[paper_id]['bib_title']] 
            self.paper_features[paper_id]['paper_key'] = paper_key
            self.paper_features[paper_id]['paper_type'] = paper_type
            self.paper_features[paper_id]['paper_book_title'] = paper_book_title
            self.paper_features[paper_id]['month'] = month
            self.paper_features[paper_id]['year'] = year
            self.paper_features[paper_id]['bib_authors'] = bib_authors

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

        # author id to ciations
        self.cumulative_citations = self.author_id_to_num_citations_in_a_year() # self.cumulative_citations[author_id][year]

        # author id to academic age
        self.first_pub_year = self.author_id_to_first_paper() # author id to first publication year first_pub_year[author_id]; used for computing NLP academic age

        # fetch gender mapping
        stanford_male_full_names, stanford_female_full_names, \
            ssa_male_first_names, ssa_female_first_names, \
                pubmed_male_first_names, pubmed_female_first_names = self.create_name_to_gender_mapping()

        # assign the gender to bib author sequence
        total, stanford_hit, ssa_hit, pubmed_hit = 0.0, 0.0, 0.0, 0.0
        for paper_id in self.paper_features:
            bib_authors = self.paper_features[paper_id]['bib_authors']
            bib_author_genders = []
            for bib_author in bib_authors:
                total += 1.0

                gender = 'unknown'
                bib_author_first_name, bib_author_last_name = [strip_non_alpha(name.lower()) for name in bib_author]

                # try using stanford list
                if (bib_author_first_name, bib_author_last_name) in stanford_male_full_names:
                    gender = 'male'
                elif (bib_author_first_name, bib_author_last_name) in stanford_female_full_names:
                    gender = 'female'

                if gender != 'unknown':
                    stanford_hit += 1.0
                else:
                    # try ssa list
                    if bib_author_first_name in ssa_male_first_names:
                        gender = 'male'
                    elif bib_author_first_name in ssa_female_first_names:
                        gender = 'female'

                    if gender != 'unknown':
                        ssa_hit += 1.0
                    else:
                        # try pubmed list
                        if bib_author_first_name in pubmed_male_first_names:
                            gender = 'male'
                        elif bib_author_first_name in pubmed_female_first_names:
                            gender = 'female'

                        if gender != 'unknown':
                            pubmed_hit += 1.0
                            
                # assigning genders
                bib_author_genders.append(gender)

            self.paper_features[paper_id]['bib_author_genders'] = bib_author_genders

        print(f"Stanford Hit: {stanford_hit/total} | SSA Hit: {ssa_hit/total} | PubMed Hit: {pubmed_hit/total}")

    def author_id_to_num_citations_in_a_year(self):
        citations = dict() # accessed as citations[author_id][1997]

        for paper_id in self.paper_features:
            author_ids = [auth_id_auth_name[0] for auth_id_auth_name in self.paper_features[paper_id]['sem_authors'] if auth_id_auth_name != ['']] # [[auth_1_id, auth_1], [auth_2_id, auth_2]]
            for author_id in author_ids:
                if author_id not in citations:
                    citations[author_id] = dict()
        
        min_paper_id_year, max_paper_id_year = 5000, -1
        for paper_id in self.paper_to_references:
            paper_id_year = int(self.paper_features[paper_id]['year'])
            min_paper_id_year = min(paper_id_year, min_paper_id_year)
            max_paper_id_year = max(paper_id_year, max_paper_id_year)
            for ref_paper_id in self.paper_to_references[paper_id]: # paper_id increases the citation count of every ref_paper_id's author by 1
                ref_author_ids = [auth_id_auth_name[0] for auth_id_auth_name in self.paper_features[ref_paper_id]['sem_authors'] if auth_id_auth_name != ['']]
                for ref_author_id in ref_author_ids:
                    if paper_id_year not in citations[ref_author_id]:
                        citations[ref_author_id][paper_id_year] = 0
                    citations[ref_author_id][paper_id_year] += 1

        # cumulate the citation uptil x year
        for author_id in citations:
            cum_citation_count_dict, cum_citation_count = dict(), 0
            for year in range(min_paper_id_year, max_paper_id_year + 1):
                if year in citations[author_id]:
                    cum_citation_count += citations[author_id][year]
                cum_citation_count_dict[year] = cum_citation_count
            citations[author_id] = cum_citation_count_dict

        return citations # cumulated over years

    def author_id_to_first_paper(self):
        first_pub = dict() # accessed as first_pub[author_id] => returns an integer indicating year of first publication

        # skips unknown authors (authors with no semantic scholar paper ID)
        for paper_id in self.paper_features:
            author_ids = [auth_id_auth_name[0] for auth_id_auth_name in self.paper_features[paper_id]['sem_authors'] if auth_id_auth_name != ['']] # [[auth_1_id, auth_1], [auth_2_id, auth_2]]
            paper_id_year = int(self.paper_features[paper_id]['year'])
            for author_id in author_ids:
                if author_id not in first_pub:
                    first_pub[author_id] = 5000 # assining some max year
                first_pub[author_id] = min(first_pub[author_id], paper_id_year)

        return first_pub 

    def create_name_to_gender_mapping(self):

        # stanford list
        stanford_male_full_names, stanford_female_full_names = [], []
        with open('../gender_dataset/stanford/acl-male.txt') as f:
            for full_name in f:
                full_name_split = [name.strip() for name in full_name.split(',')]
                last_name, first_name = full_name_split[0], ''.join(full_name_split[1:])
                stanford_male_full_names.append((strip_non_alpha(first_name.lower()), strip_non_alpha(last_name.lower())))
        with open('../gender_dataset/stanford/acl-female.txt') as f:
            for full_name in f:
                full_name_split = [name.strip() for name in full_name.split(',')]
                last_name, first_name = full_name_split[0], ''.join(full_name_split[1:])
                stanford_female_full_names.append((strip_non_alpha(first_name.lower()), strip_non_alpha(last_name.lower())))
        
        # ssa list
        ssa_male_first_names, ssa_female_first_names = [], []
        with open('../gender_dataset/ssa/ssa_male_first_names.txt') as f:
            for first_name in f:
                first_name = first_name.strip()
                ssa_male_first_names.append(strip_non_alpha(first_name.lower()))
        with open('../gender_dataset/ssa/ssa_female_first_names.txt') as f:
            for first_name in f:
                first_name = first_name.strip()
                ssa_female_first_names.append(strip_non_alpha(first_name.lower()))

        # pubmed list
        pubmed_male_first_names, pubmed_female_first_names = [], []
        with open('../gender_dataset/pubmed/pubmed_genni_male_first_names.txt') as f:
            for first_name in f:
                first_name = first_name.strip()
                pubmed_male_first_names.append(strip_non_alpha(first_name.lower()))
        with open('../gender_dataset/pubmed/pubmed_genni_female_first_names.txt') as f:
            for first_name in f:
                first_name = first_name.strip()
                pubmed_female_first_names.append(strip_non_alpha(first_name.lower()))
        
        return stanford_male_full_names, stanford_female_full_names, \
            ssa_male_first_names, ssa_female_first_names, \
                pubmed_male_first_names, pubmed_female_first_names
        
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

    def paper_id_to_country_cited_count(self):
        paper_id_to_country_cited = dict() # paper_id to country_cited counts
        for paper_id in self.paper_to_references:
            paper_id_to_country_cited[paper_id] = dict()
            ref_paper_ids = self.paper_to_references[paper_id]
            for ref_paper_id in ref_paper_ids: # for each paper id, iterate over all the referenced paper ids
                ref_countries = self.paper_features[ref_paper_id]['countries']
                for ref_country in ref_countries: # for each referenced paper, iterate over all the countries
                    if ref_country not in paper_id_to_country_cited:
                        paper_id_to_country_cited[paper_id][ref_country] = 0
                    paper_id_to_country_cited[paper_id][ref_country] += 1
        return paper_id_to_country_cited

    def country_to_country_fraction(self, save_fpath, k = 10):
        '''
            For top-k countries computes the fraction of references (of all the references of country A) of country A to country B
        '''
        paper_id_to_country_cited = self.paper_id_to_country_cited_count()
        country_to_paper_ids = self.country_to_publications()
        country_to_paper_ids = {k: country_to_paper_ids[k] for k in country_to_paper_ids if k not in self.company_names} # filter out company names
        top_k_countries = [country_1 for country_1, country_1_paper_ids in sorted(country_to_paper_ids.items(), key=lambda x: -len(x[1]))[:k]] # top k publishing countries

        country_to_ref_country_counts = dict()
        for country in top_k_countries:
            if country not in country_to_ref_country_counts:
                country_to_ref_country_counts[country] = dict()
            for paper_id in country_to_paper_ids[country]: # iterating over all the paper_ids of country

                all_counts = 0
                for referenced_country in paper_id_to_country_cited[paper_id]:
                    all_counts += paper_id_to_country_cited[paper_id][referenced_country]
                if 'all' not in country_to_ref_country_counts[country]: # all country to all references count
                    country_to_ref_country_counts[country]['all'] = []
                country_to_ref_country_counts[country]['all'].append(all_counts)

                for ref_country in top_k_countries:
                    ref_country_count = 0
                    if ref_country in paper_id_to_country_cited[paper_id]:
                        ref_country_count = paper_id_to_country_cited[paper_id][ref_country]

                    if ref_country not in country_to_ref_country_counts[country]: # all country to all references count
                        country_to_ref_country_counts[country][ref_country] = []
                    country_to_ref_country_counts[country][ref_country].append(ref_country_count)    
                    
        for country in top_k_countries:
            paper_count = len(country_to_ref_country_counts[country]['all'])
            for ref_country in top_k_countries:
                assert(paper_count==len(country_to_ref_country_counts[country][ref_country]))

        with open(save_fpath, 'w') as f:
            json.dump(country_to_ref_country_counts, f)

    def cont_1_to_cont_2_auth_edges_and_names(self, country_1_paper_ids, country_2_paper_ids, dominant_edges_thresold, thresold_type):
        author_id_to_author_name, author_id_to_references_count, edges_dict = dict(), dict(), dict()
        for paper_id in country_1_paper_ids:
            name_and_id_list = self.paper_features[paper_id]['sem_authors'] # [[auth_1_id, auth_1], [auth_2_id, auth_2]]
            for cited_paper_id in self.paper_to_references[paper_id]:
                if cited_paper_id in country_2_paper_ids: # relevant edge | country_1 -> country_2
                    cited_name_and_id_list = self.paper_features[cited_paper_id]['sem_authors']
                    # add some edges.
                    for author_id_author_name in name_and_id_list:
                        if len(author_id_author_name) < 2:
                            print(f"*********************************** {author_id_author_name}")
                            continue
                        author_id, author_name = author_id_author_name

                        for cited_author_id_cited_author_name in cited_name_and_id_list:
                            if len(cited_author_id_cited_author_name) < 2:
                                print(f"*********************************** {cited_author_id_cited_author_name}")
                                continue
                            cited_author_id, cited_author_name = cited_author_id_cited_author_name
                            
                            if author_id=='None' or cited_author_id=='None': # discarding edge because author id not known for either of the author
                                continue
                            if author_id==cited_author_id: # discarding edge because its a self loop
                                continue

                            if author_id in author_id_to_author_name:
                                assert(author_id_to_author_name[author_id]==author_name), f"Author ID matching multiple author names | {author_id} => [{author_name}, {author_id_to_author_name[author_id]}]"
                            else:
                                author_id_to_author_name[author_id] = author_name

                            if cited_author_id in author_id_to_author_name:
                                assert(author_id_to_author_name[cited_author_id]==cited_author_name), f"Author ID matching multiple author names | {cited_author_id} => [{cited_author_name}, {author_id_to_author_name[cited_author_id]}]"
                            else:
                                author_id_to_author_name[cited_author_id] = cited_author_name

                            key = f'{author_id}#{cited_author_id}'
                            if key not in edges_dict:
                                edges_dict[key] = 0
                            edges_dict[key] += 1

                            if author_id not in author_id_to_references_count:
                                author_id_to_references_count[author_id] = 0
                            author_id_to_references_count[author_id] += 1

        # do some thresolding
        for edge in edges_dict:

            if thresold_type == 'count':
                if edges_dict[edge] < dominant_edges_thresold: # only consider edges >=dominant_edges_thresold
                    edges_dict[edge] = 0

            if thresold_type == 'fraction':
                author_id, cited_author_id = edge.split('#')
                if 100.0 * edges_dict[edge] / author_id_to_references_count[author_id] < dominant_edges_thresold:
                    edges_dict[edge] = 0

        return author_id_to_author_name, edges_dict

    def author_undirected_graph(self, country_pair, dominant_edges_thresold = 0, thresold_type = 'count'):
        '''
            Assumes a pair of countries; 
            Identifies paper-citations such that they are in (country_1, country_2) or (country_2, country_1);
            Creates a graph with authors as nodes and edges only identified in last step;
            Returns set of vertices and edges of this graph as list: [node_1, node_2, ..., node_k] and  [(node_3, node_2), ..., (node_5, node_10)].
        '''
        assert(len(country_pair)==2), "Specify exactly two countires"

        country_to_paper_ids = self.country_to_publications()
        country_1_paper_ids, country_2_paper_ids = country_to_paper_ids[country_pair[0]], country_to_paper_ids[country_pair[1]]
        
        # discuss about papers related with multiple countries?
        author_id_to_author_name_1_2, edges_dict_1_2 = self.cont_1_to_cont_2_auth_edges_and_names(country_1_paper_ids, country_2_paper_ids, dominant_edges_thresold, thresold_type)
        print(f"Identified edges from {country_pair[0]} to {country_pair[1]}...")
        author_id_to_author_name_2_1, edges_dict_2_1 = self.cont_1_to_cont_2_auth_edges_and_names(country_2_paper_ids, country_1_paper_ids, dominant_edges_thresold, thresold_type)
        print(f"Identified edges from {country_pair[1]} to {country_pair[0]}...")
        author_id_to_author_name = {**author_id_to_author_name_1_2, **author_id_to_author_name_2_1}
        
        nodes, edges = set(), set()
        # accumulating nodes
        for author_id in author_id_to_author_name:
            nodes.add(author_id)
        # accumulating edges
        for edge_1_2 in edges_dict_1_2:
            if edges_dict_1_2[edge_1_2] <= 0: # not a dominant edge
                continue
            author_id, cited_author_id = edge_1_2.split('#')
            reversed_edge_1_2 = f'{cited_author_id}#{author_id}'
            if reversed_edge_1_2 in edges_dict_2_1 and edges_dict_2_1[reversed_edge_1_2] > 0: # add a bidirectional edge if reverse edge is a domainat edge in edges_dict_2_1
                if author_id < cited_author_id:
                    edges.add((author_id, cited_author_id))
                else:
                    edges.add((cited_author_id, author_id))
        print(f"Computed all the bi-directional edges...")

        return list(nodes), list(edges), author_id_to_author_name
            
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



