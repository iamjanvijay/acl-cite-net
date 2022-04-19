import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import json
import os
from math import log

def plot_2d_matrix(array, row_indices, column_indices, output_folder, file_name):
    '''
        Takes list of list (array) and plots a heat-map (confusion matrix).
    '''
    df_cm = pd.DataFrame(array, index = [i for i in row_indices], columns = [i for i in column_indices])
    plt.figure(figsize = (10,7))
    figure = sns.heatmap(df_cm, annot=True, cmap="OrRd", robust=True)
    figure.get_figure().savefig(os.path.join(output_folder, file_name))

# def plot_time_series()

def main(args):
    if args.plot_inter_country_cite_density_stats: # for density metrics of citation subgraphs
        index, country_to_index = 0, dict()
        with open(args.input_file) as f:
            stats_dict = json.load(f)

            for country_1_country_2 in stats_dict: 
                country_1, country_2 = country_1_country_2.split('#')
                if country_1 not in country_to_index:
                    country_to_index[country_1] = index
                    index += 1
                if country_2 not in country_to_index:
                    country_to_index[country_2] = index
                    index += 1

            array_w_year = [[0 for j in range(index)] for i in range(index)]
            array_wo_year = [[0 for j in range(index)] for i in range(index)]
            inv_country_to_index = {v: k for k, v in country_to_index.items()}
            row_indices = column_indices = [inv_country_to_index[i] for i in range(index)]

            for country_1_country_2 in stats_dict: 
                country_1, country_2 = country_1_country_2.split('#')
                country_1_index, country_2_index = country_to_index[country_1], country_to_index[country_2]
                array_w_year[country_1_index][country_2_index] = 100 * stats_dict[country_1_country_2]['citation_density_w_year'] # country_1 cites country_2 stats
                array_wo_year[country_1_index][country_2_index] = 100 * stats_dict[country_1_country_2]['citation_density_wo_year'] # country_1 cites country_2 stats
                print(f"Citation density of {country_1} citing (with year) {country_2}: {100 * stats_dict[country_1_country_2]['citation_density_w_year']}")
                print(f"Citation density of {country_1} citing (without year) {country_2}: {100 * stats_dict[country_1_country_2]['citation_density_wo_year']}")

            plot_2d_matrix(array_w_year, row_indices, column_indices, args.output_folder, os.path.basename(args.input_file).split('.')[0] + '_w_year.png')
            plot_2d_matrix(array_wo_year, row_indices, column_indices, args.output_folder, os.path.basename(args.input_file).split('.')[0] + '_wo_year.png')

    if args.plot_country_to_referenced_country_fraction:
        with open(args.input_file) as f:
            stats_dict = json.load(f)
            first_covert_counts_to_fraction = False
            top_countires = sorted([country for country in stats_dict if country != 'all'])
            array = [[0 for j in range(len(top_countires))] for i in range(len(top_countires))]
            country_to_idx = {country: idx for idx, country in enumerate(top_countires)}
   
            if first_covert_counts_to_fraction:
                for country in top_countires:
                    for ref_country in top_countires:
                            for paper_idx in range(len(stats_dict[country][ref_country])):
                                if stats_dict[country]['all'][paper_idx] != 0: # if paper has total non-zero references
                                    stats_dict[country][ref_country][paper_idx] = stats_dict[country][ref_country][paper_idx] / float(stats_dict[country]['all'][paper_idx])
                    for paper_idx in range(len(stats_dict[country]['all'])):
                        if stats_dict[country]['all'][paper_idx] != 0: # if paper has total non-zero references
                            stats_dict[country]['all'][paper_idx] = 1.0
            
            for country in top_countires:
                for ref_country in top_countires:
                    array[country_to_idx[country]][country_to_idx[ref_country]] = 100 * sum(stats_dict[country][ref_country]) / sum(stats_dict[country]['all'])
            
            plot_2d_matrix(array, top_countires, top_countires, args.output_folder, os.path.basename(args.input_file).split('.')[0] + '.png')
                        
    if args.plot_time_country_cite_stats:
        with open(args.input_file) as f:
            stats_dict = json.load(f)

            # get list of countries
            print("stats_dict", stats_dict)
            for year in stats_dict:
                list_of_countries = [country for country in stats_dict[year]]
                break

            # create paper count and citation count data-frame
            paper_count_df_dict, citation_count_df_dict = dict(), dict()
            for year in sorted(stats_dict):
                if 'year' not in paper_count_df_dict:
                    paper_count_df_dict['year'], citation_count_df_dict['year'] = [], []
                paper_count_df_dict['year'].append(str(year))
                citation_count_df_dict['year'].append(str(year))

                for country in stats_dict[year]:
                    if country not in paper_count_df_dict:
                        paper_count_df_dict[country] = []
                        citation_count_df_dict[country] = []
                    paper_count_df_dict[country].append(stats_dict[year][country][0]) # paper count
                    citation_count_df_dict[country].append(stats_dict[year][country][1]) # citation count
            paper_count_df, citation_count_df = pd.DataFrame(paper_count_df_dict), pd.DataFrame(citation_count_df_dict)

        # colors = ['black', 'darkgrey', 'maroon', 'red', 'sandybrown', 'olive', 'yellow', 'lime', 'navy', 'magenta']
        # for country, color in zip(list_of_countries, colors):
        #     paper_count_df[country].plot(label=country, color=color)
        # plt.title('Paper Count from 2000 to 2021')
        # plt.xlabel('Years')
        # plt.legend()
        # plt.savefig(os.path.join(args.output_folder, 'paper_count_over_years.png'))

        colors = ['black', 'darkgrey', 'maroon', 'red', 'sandybrown', 'olive', 'yellow', 'lime', 'navy', 'magenta']
        for country, color in zip(list_of_countries, colors):
            citation_count_df[country].plot(label=country, color=color)
        plt.title('Citation Count from 2000 to 2021')
        plt.xlabel('Years')
        plt.legend()
        plt.savefig(os.path.join(args.output_folder, 'citation_count_over_years.png'))

    if args.plot_clique_count_heatmap:
        clique_size = 6

        with open(args.input_file) as f:
            stats_dict = json.load(f)
        
            index, country_to_index = 0, dict()
            for country_pair in stats_dict:
                country_1, country_2 = country_pair.split('#')
                if country_1 not in country_to_index:
                    country_to_index[country_1] = index
                    index += 1
                if country_2 not in country_to_index:
                    country_to_index[country_2] = index
                    index += 1

            array = [[0 for j in range(index)] for i in range(index)]
            inv_country_to_index = {v: k for k, v in country_to_index.items()}
            row_indices = column_indices = [inv_country_to_index[i] for i in range(index)]

            for country_pair in stats_dict:
                node_count, edge_count, author_id_to_author_name, clique_len_to_count = stats_dict[country_pair]["node_count"], stats_dict[country_pair]["edge_count"], stats_dict[country_pair]["author_id_to_author_name"], stats_dict[country_pair]["clique_len_to_count"]
                
                country_1, country_2 = country_pair.split('#')
                country_1_index, country_2_index = country_to_index[country_1], country_to_index[country_2]
                array[country_1_index][country_2_index] = array[country_2_index][country_1_index] = float(clique_len_to_count[str(clique_size)] if str(clique_size) in clique_len_to_count else 0) / node_count

            plot_2d_matrix(array, row_indices, column_indices, args.output_folder, os.path.basename(args.input_file).split('.')[0] + f'_clique_size_{clique_size}.png')

                
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot_inter_country_cite_density_stats", action='store_true', default=False,
                    help='wheather to plot the 2-d heatmap from input json file')
    parser.add_argument("--plot_time_country_cite_stats", action='store_true', default=False,
                    help='wheather to plot the citation densities and paper counts for top-10 publishing countries')
    parser.add_argument("--plot_country_to_referenced_country_fraction", action='store_true', default=False,
                    help='wheather to plot the citation fractions for top-10 publishing countries')
    parser.add_argument("--plot_clique_count_heatmap", action='store_true', default=False,
                    help='plot the heatmap consisting of counts of cliques in subgraph (citation edges allowed only for a pair of countries) of authors')
    parser.add_argument("--input_file", type=str, required=True, 
                        help='path to file with stats') # like: './downloads/inter_country_cited_count.json'
    parser.add_argument("--output_folder", type=str, default='./downloads', 
                        help='path to output_folder')
    args = parser.parse_args()
    
    main(args)

