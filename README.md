# ACL-Cite-Net
This repo contains codes for the following paper:

Mukund Rungta, Janvijay Singh, Saif M. Mohammad, Diyi Yang: Geographic Citation Gaps in NLP Research, EMNLP 2022
If you would like to refer to it, please cite the paper mentioned above. 

## Getting Started
These instructions will get you running the codes to generate data for each analysis.

### Downloading all PDFs from ACL Anthology
```python code/main.py --download_pdfs```

### Dump bib details of all papers
```python code/main.py --dump_bib_details```

### Fetch details from Semantics Scholar
```python code/main.py --fetch_paper_details --clean_paper_details```

### Creating the Citation Network
```python code/main.py --create_cite_net```

### Generating data for each analysis
Following parameters needs to be set inorder to generate the corresponding data for visualization. `True` can be changed to `False` if the particular data does not needs to be generated.

```
'dump_country_paper_count': True, # count number of papers from each country
'dump_year_and_avg_citation_of_country': True, # average citation recieved by the country across years
'dump_year_and_avg_citation_of_region': True, # average citation recieved by regions across years
'dump_paper_age_to_citations_of_country': True, # average citation recieved by the country varied across age of paper
'dump_paper_age_to_citations_of_region': True, # average citation recieved by the region varied across age of paper
'dump_regression_features': True, # features of papers to model regression analysis 
'dump_top_10_publishing_country_heat_map': True, # heat map depicting inter-country citation pattern for top-10 countries
'dump_regions_heat_map': True, # heat map to capture the collaboration between different regions
'dump_gini_coeff_over_years': True, # Gini-coefficient to capture dispersion of citation fractions among top-10 publishing countries.
'dump_gini_coeff_over_years_regions': True, # Gini-coefficient to capture collaboration among different region
'dump_area_of_research_countries': True, # Statistics of citation of papers published by different countries across different areas of NLP
'dump_venue_of_publication_countries': True # Statistics of citation of papers published by different countries in different venues
```

## Visualization
All the data required for visualizing analysis of each question can be found it `download` folder. 
We use Tableau to plot the results for efficient and interactive visualization. All the plots presented in this work can be accessed from
following Tableau Public profiles:

https://public.tableau.com/app/profile/gdnlp






