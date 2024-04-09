import json



# combine the dataset/nyt/train_data.json and dataset/nyt/valid_data.json

def combine_train_valid():
    train_data = json.load(open('dataset/webnlg/train_data.json'))
    valid_data = json.load(open('dataset/webnlg/valid_data.json'))
    train_data.extend(valid_data)
    with open('dataset/webnlg/train_valid_data.json', 'w') as f:
        json.dump(train_data, f)


if __name__ == '__main__':
    combine_train_valid()
    print("Done!")