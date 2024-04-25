import json

# Path to the JSON file
file_path = 'dataset/CoNLL04/train_split.json'

# Load the JSON data
with open(file_path, 'r', encoding='utf-8') as file:
    data = json.load(file)

# Initialize counters
total_samples = len(data)
loc_count = 0
per_count = 0
org_count = 0
country_count = 0

# Iterate over each sample in the dataset
for sample in data:
    for ent in sample.get('relation_list', []):
        if ent.get('subj_ner') == 'LOC' or ent.get('obj_ner') == 'LOC':
            loc_count += 1
        if ent.get('subj_ner') == 'PER' or ent.get('obj_ner') == 'PER':
            per_count += 1
        if ent.get('subj_ner') == 'ORG' or ent.get('obj_ner') == 'ORG':
            org_count += 1
        if ent.get('subj_ner') == 'COUNTRY' or ent.get('obj_ner') == 'COUNTRY':
            country_count += 1

# Print the results
print(f"Total samples: {total_samples}")
print(f"LOC count: {loc_count}")
print(f"PER count: {per_count}")
print(f"ORG count: {org_count}")
print(f"COUNTRY count: {country_count}")
