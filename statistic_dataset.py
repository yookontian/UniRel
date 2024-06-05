import json

# datasets = ["nyt", "sem_eval_2010_task_8", "webnlg", "CoNLL04"]
datasets = ["nyt"]
for data_name in datasets:
    # Path to the JSON file
    file_path = f'dataset/nyt/original/{data_name}/test_data.json'
    print(f"Dataset: {data_name}")
    # Load the JSON data
    with open(file_path, 'r', encoding='utf-8') as file:
        data = json.load(file)

    # Initialize counters
    total_samples = len(data)
    loc_count = 0
    per_count = 0
    org_count = 0
    country_count = 0
    triple_count = 0
    if data_name == "nyt":
        import dataprocess.rel2text

        pred2text = dataprocess.rel2text.nyt_rel2text
        idx = 0
        pred2idx = {}
        for k in pred2text:
            pred2idx[k] = idx
            idx += 1
        loc_head = [7, 10, 11, 23]
        loc_tail = [4, 8, 9, 10, 11, 12, 18, 19, 22]
        org_head = [0, 1, 2, 3, 4, 22]
        org_tail = [5, 6, 20, 23]
        per_head = [5, 6, 12, 15, 16, 17, 18, 19, 20, 21]
        per_tail = [0, 1, 3, 14, 15]
        country_head = [8, 9]
        country_tail = [8, 13, 17]
        for sample in data:
            for ent in sample.get('relation_list', []):
                triple_count += 1
                pred_idx = pred2idx[ent.get('predicate')]
                if pred_idx in loc_head:
                    loc_count += 1
                if pred_idx in loc_tail:
                    loc_count += 1
                if pred_idx in per_head:
                    per_count += 1
                if pred_idx in per_tail:
                    per_count += 1
                if pred_idx in org_head:
                    org_count += 1
                if pred_idx in org_tail:
                    org_count += 1
                if pred_idx in country_head:
                    country_count += 1
                if pred_idx in country_tail:
                    country_count += 1

    else:
        # Iterate over each sample in the dataset
        for sample in data:
            for ent in sample.get('relation_list', []):
                triple_count += 1
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
    print(f"Triple count: {triple_count}")
    print(f"LOC count: {loc_count}")
    print(f"PER count: {per_count}")
    print(f"ORG count: {org_count}")
    print(f"COUNTRY count: {country_count}")
    print("--------------------")
