#-*- coding: UTF-8 -*-
"""
A pro-processing for the original dataset. I used spacy to add NER tags to the dataset.
Therefore, the data_processor need to be modified, the processes for NYT and WebNLG are different.
"""



import spacy

import tqdm

spacy.prefer_gpu()
nlp = spacy.load("en_core_web_sm")
ner = nlp.get_pipe("ner")
"""
texts = [
    "Net income was $9.4 million compared to the prior year of $2.7 million.",
    "Revenue exceeded twelve billion dollars, with a loss of $1b.",
]
doc = nlp(texts[0])

processed = ner(doc)
# output the entities and their labels
for ent in processed.ents:
    print(ent.text, ent.label_)
"""
# load the json file in dataset/webnlg/test_data.json and print the keys
import json
with open('/home/tian/Projects/UniRel/dataset/webnlg/train_split.json', 'r', encoding='utf-8') as f:
    samples = json.load(f)
# print(samples[0].keys())
# print(samples[0]['text'])
# print(samples[0]['relation_list'])
# print(samples[0]['relation_list'][0].keys())
# print(samples[0]['entity_list'])
# print(samples[0]['entity_list'][0].keys())
# print(samples[0]['text'][0:11])

new_list = []
print(samples[0]['text'])

for sample in tqdm.tqdm(samples):

    item = sample

    doc = nlp(item['text'])
    processed = ner(doc)



    # LOC, PER, ORG, COUNTRY
    sentence_ner = {}

    for ent in processed.ents:
        # print(ent.text, ent.label_)
        if ent.label_ == "LOC":
            sentence_ner[(ent.start_char, ent.end_char)] = "LOC"
        elif ent.label_ == "PERSON":
            # print the character position of the entity
            sentence_ner[(ent.start_char, ent.end_char)] = "PER"
        elif ent.label_ == "ORG":
            sentence_ner[(ent.start_char, ent.end_char)] = "ORG"
        elif ent.label_ == "GPE":
            sentence_ner[(ent.start_char, ent.end_char)] = "COUNTRY"
    for idx, t in enumerate(item['relation_list']):
        if tuple(t['subj_char_span']) in sentence_ner:
            item['relation_list'][idx]['subj_ner'] = sentence_ner[tuple(t['subj_char_span'])]
        else:
            item['relation_list'][idx]['subj_ner'] = "default"
        if tuple(t['obj_char_span']) in sentence_ner:
            item['relation_list'][idx]['obj_ner'] = sentence_ner[tuple(t['obj_char_span'])]
        else:
            item['relation_list'][idx]['obj_ner'] = "default"

    new_list.append(item)


# save the new_list to a new json file as dataset/webnlg/test_data_ner.json
with open('/home/tian/Projects/UniRel/dataset/webnlg/train_split_ner.json', 'w', encoding='utf-8') as f:
    json.dump(new_list, f, ensure_ascii=False)

# --> next: valid_data, modify the dataset file name, and modify the data_processor

print("done!")