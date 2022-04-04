import seaborn as sns
import pandas as pd
import matplotlib.pyplot as plt
import argparse
import json
import os

def plot_2d_matrix(array, row_indices, column_indices, output_folder, file_name):
    '''
        Takes list of list (array) and plots a heat-map (confusion matrix).
    '''
    df_cm = pd.DataFrame(array, index = [i for i in row_indices], columns = [i for i in column_indices])
    plt.figure(figsize = (10,7))
    figure = sns.heatmap(df_cm, annot=True, cmap="OrRd")
    figure.get_figure().savefig(os.path.join(output_folder, file_name))

def main(args):
    if args.plot_inter_country_cite_stats:
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
                
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--plot_inter_country_cite_stats", action='store_true', default=False,
                    help='wheather to plot the 2-d heatmap from input json file')
    parser.add_argument("--input_file", type=str, required=True, 
                        help='path to file with stats') # like: './downloads/inter_country_cited_count.json'
    parser.add_argument("--output_folder", type=str, default='./downloads', 
                        help='path to output_folder')
    args = parser.parse_args()
    
    main(args)

