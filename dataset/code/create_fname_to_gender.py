# Sample Usage: python code/create_fname_to_gender.py
import os
import csv
import sys

csv.field_size_limit(sys.maxsize)
COMPUTE_ASS_NAMES_FROM_SSA = True
COMPUTE_ASS_NAMES_FROM_PUBMED = True

def strip_non_alpha(text):
    return ''.join([i for i in text if i.isalpha()])

# SSA dataset
if COMPUTE_ASS_NAMES_FROM_SSA:
    thresold_perc = 95 # >=95 included
    folder_path = '../gender_dataset/ssa/names'
    fnames = [fname for fname in os.listdir(folder_path) if fname.startswith('yob') and fname.endswith('.txt')]
    first_name_to_count = dict() # name_to_count['Mary] = (m_count, f_count)
    male_first_names, female_first_names = [],[]

    for fname in fnames:
        fpath = os.path.join(folder_path, fname)
        with open(fpath) as f:
            for line in f:
                first_name, gender, count = line.strip().split(',') # Mary,F,7065

                first_name, gender = [x.lower() for x in [strip_non_alpha(first_name), gender]]
                count = int(count)

                assert(gender in ['m', 'f'] and count > 0)

                if first_name not in first_name_to_count:
                    first_name_to_count[first_name] = [0, 0]
                index = 0 if gender=='m' else 1
                first_name_to_count[first_name][index] += count
    print(f"Total First Names Read: {len(first_name_to_count)}")

    for first_name in first_name_to_count:
        m_count, f_count = first_name_to_count[first_name]
        m_perc = (100.0 * m_count) / (m_count + f_count)
        f_perc = 100.0 - m_perc

        if m_perc >= thresold_perc:
            male_first_names.append(first_name)
        if f_perc >= thresold_perc:
            female_first_names.append(first_name)

    with open(os.path.join('../gender_dataset/ssa', 'ssa_male_first_names.txt'), 'w') as f:
        for male_first_name in male_first_names:
            f.write(male_first_name.strip() + '\n')
        print(f"Total Male First Names: {len(male_first_names)}")

    with open(os.path.join('../gender_dataset/ssa', 'ssa_female_first_names.txt'), 'w') as f:
        for female_first_name in female_first_names:
            f.write(female_first_name.strip() + '\n')
        print(f"Total Female First Names: {len(female_first_names)}")

if COMPUTE_ASS_NAMES_FROM_PUBMED:
    gender_from = 'genni'
    # gender_from = 'ssn'
    thresold_perc = 95 # >=95 included
    first_name_to_count = dict() # name_to_count['Mary] = (m_count, f_count)
    fpath = '../gender_dataset/pubmed/DOI-10-13012-b2idb-9087546_v1/genni-ethnea-authority2009.tsv'
    male_first_names, female_first_names = [],[]

    with open(fpath) as f:
        # tsvreader = csv.reader(f, delimiter = '\t')
        # for i, row in enumerate(tsvreader): 
        for i, line in enumerate(f):
            row = line.strip().split('\t')
            if len(row) != 10:
                print(f"Ignoring line {i}: {row}")

            if i == 0:
                continue
            _, _, _, _, last_name, first_name, _, gender_genni, _, gender_ssn = row  # auid    name    EthnicSeer      prop    lastname        firstname       Ethnea  Genni   SexMac  SSNgender
            first_name, gender_genni, gender_ssn = [x.lower() for x in [strip_non_alpha(first_name), gender_genni, gender_ssn]]

            if gender_from =='genni':
                gender = gender_genni
            else:
                gender = gender_ssn

            assert(gender in ['-', 'm', 'f']), f"The gender is: {gender}"
            if gender == '-':
                continue

            index = 0 if gender=='m' else 1
            if first_name not in first_name_to_count:
                first_name_to_count[first_name] = [0, 0]
            first_name_to_count[first_name][index] += 1
    
    print(f"Total Names: {i}")
    print(f"Total First Names: {len(first_name_to_count)}")
    for first_name in first_name_to_count:
        m_count, f_count = first_name_to_count[first_name]
        m_perc = (100.0 * m_count) / (m_count + f_count)
        f_perc = 100.0 - m_perc

        if m_count + f_count <= 1:
            continue

        if m_perc >= thresold_perc:
            male_first_names.append(first_name)
        if f_perc >= thresold_perc:
            female_first_names.append(first_name)

    with open(os.path.join('../gender_dataset/pubmed', f'pubmed_{gender_from}_male_first_names.txt'), 'w') as f:
        for male_first_name in male_first_names:
            f.write(male_first_name.strip() + '\n')
        print(f"Total Male First Names: {len(male_first_names)}")

    with open(os.path.join('../gender_dataset/pubmed', f'pubmed_{gender_from}_female_first_names.txt'), 'w') as f:
        for female_first_name in female_first_names:
            f.write(female_first_name.strip() + '\n')
        print(f"Total Female First Names: {len(female_first_names)}")

    


            



    
