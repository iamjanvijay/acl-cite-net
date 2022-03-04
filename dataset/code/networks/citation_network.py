import csv
import os

class CitationNet:
    def __init__(self, paper_details_filepath, references_filepath):
        self.paper_to_references = dict() # paperID => [list of references of paper with paperID]
        self.paper_to_citedby = dict() # paperID => [list of papers citing paper with paperID]
        self.paper_features = dict() # paperID => [dictonary of features of paper with paperID]

        if os.path.exists(paper_details_filepath): # Read the details of all the papers.
            with open(paper_details_filepath) as csvfile:
                csvreader = csv.reader(csvfile)
                for row in csvreader:
                    paper_id, bib_title, ret_title, authors, fuzzy_score, request_type = row 
                    authors = [author_and_id.strip().split('#') for author_and_id in authors.strip().split('%')] # [[auth_1, auth_1_id], [auth_2, auth_2_id]]
                    self.paper_to_references[paper_id] = set()
                    self.paper_features[paper_id] = {'bib_title': bib_title, 'sem_title': ret_title, 'authors': authors}

        if os.path.exists(references_filepath):
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
