import collections
import logging
import os
import sys
import csv
import glob
from dataclasses import dataclass, field
from typing import Optional
from utils import data_collator, FreezeLayerCallback

import transformers
import numpy as np
import torch
# from torch.utils.tensorboard import SummaryWriter

import wandb

from transformers import (BertTokenizerFast, BertModel, Trainer,
                          TrainingArguments, BertConfig, BertLMHeadModel)

from transformers.hf_argparser import HfArgumentParser
from transformers import EvalPrediction, set_seed

from dataprocess.data_processor import UniRelDataProcessor
from dataprocess.dataset import UniRelDataset, UniRelSpanDataset

from model.model_transformers import UniRelModel
from model.model_transformers_ner import UniRelModel_ner

from dataprocess.data_extractor import *
from dataprocess.data_metric import *

os.environ["TOKENIZERS_PARALLELISM"] = "false"

UniRelModel = UniRelModel_ner
# freeze_callback = FreezeLayerCallback()

DataProcessorDict = {
    "nyt_all_sa": UniRelDataProcessor,
    "unirel_span": UniRelDataProcessor
}

DatasetDict = {
    "nyt_all_sa": UniRelDataset,
    "unirel_span": UniRelSpanDataset 
}

ModelDict = {
    "nyt_all_sa": UniRelModel,
    "unirel_span": UniRelModel
}

PredictModelDict = {
    "nyt_all_sa": UniRelModel,
    "unirel_span": UniRelModel
}

DataMetricDict = {
    "nyt_all_sa": unirel_metric,
    "unirel_span": unirel_span_metric
}

PredictDataMetricDict = {
    "nyt_all_sa": unirel_metric,
    "unirel_span": unirel_span_metric

}

DataExtractDict = {
    "nyt_all_sa": unirel_extractor,
    "unirel_span": unirel_span_extractor

}

LableNamesDict = {
    "nyt_all_sa": [ "tail_label"],
    "unirel_span":["head_label", "tail_label", "span_label"],
}

InputFeature = collections.namedtuple(
    "InputFeature", ["input_ids", "attention_mask", "token_type_ids", "label"])

logger = transformers.utils.logging.get_logger(__name__)

class MyCallback(transformers.TrainerCallback):
    "A callback that prints a message at the beginning of training"

    def on_epoch_begin(self, args, state, control, **kwargs):
        print("Epoch start")


    def on_epoch_end(self, args, state, control, **kwargs):
        print("Epoch end")



@dataclass
class RunArguments:
    """Arguments pretraining to which model/config/tokenizer we are going to continue training, or train from scratch.
    """
    model_dir: Optional[str] = field(
        default=None,
        metadata={
            "help":
            "The model checkpoint for weights initialization."
            "Don't set if you want to train a model from scratch."
        })
    config_path: Optional[str] = field(
        default=None,
        metadata={
            "help":
            "The configuration file of initialization parameters."
            "If `model_dir` has been set, will read `model_dir/config.json` instead of this path."
        })
    vocab_path: Optional[str] = field(
        default=None,
        metadata={
            "help":
            "The vocabulary for tokenzation."
            "If `model_dir` has been set, will read `model_dir/vocab.txt` instead of this path."
        })
    dataset_dir: str = field(
        metadata={"help": "Directory where data set stores."}, default=None)
    max_seq_length: Optional[int] = field(
        default=100,
        metadata={
            "help":
            "The maximum total input sequence length after tokenization. Longer sequences"
            "will be truncated. Default to the max input length of the model."
        })
    task_name: str = field(metadata={"help": "Task name"},
                           default=None)
    do_test_all_checkpoints: bool = field(
        default=False,
        metadata={"help": "Whether to test all checkpoints by test_data"})
    test_data_type: str = field(
        metadata={"help": "Which data type to test: nyt_all_sa"},
        default=None)
    train_data_nums: int = field(
        metadata={"help": "How much data to train the model."}, default=-1)
    test_data_nums: int = field(metadata={"help": "How much data to test."},
                                default=-1)
    dataset_name: str = field(
        metadata={"help": "The dataset you want to test"}, default=-1)
    threshold: float = field(
        metadata={"help": "The threhold when do classify prediction"},
        default=-1)
    test_data_path: str = field(
        metadata={"help": "Test specific data"},
        default=None)
    checkpoint_dir : str = field(
        metadata={"help": "Test with specififc trained checkpoint"},
        default=None
    )
    is_additional_att: bool = field(
        metadata={"help": "Use additonal attention layer upon BERT"},
        default=False)
    is_separate_ablation: bool = field(
        metadata={"help": "Seperate encode text and predicate to do ablation study"},
        default=False)


if __name__ == '__main__':
    parser = HfArgumentParser((RunArguments, TrainingArguments))
    if len(sys.argv[1]) == 2 and sys.argv[1].endswith(".json"):
        run_args, training_args = parser.parse_json_file(
            json_file=os.path.abspath(sys.argv[1]))
    else:
        run_args, training_args = parser.parse_args_into_dataclasses()

    if (os.path.exists(training_args.output_dir)
            and os.listdir(training_args.output_dir) and training_args.do_train
            and not training_args.overwrite_output_dir):
        raise ValueError(
            f"Output directory ({training_args.output_dir}) already exists and not empty."
            "Use --overwrite_output_dir to overcome.")

    set_seed(training_args.seed)

    # it's merely an annotation for type checking and readability purposes.
    training_args: TrainingArguments
    run_args: RunArguments

    # Initialize configurations and tokenizer.
    added_token = [f"[unused{i}]" for i in range(1, 17)]
    # If use unused to do ablation, should uncomment this
    # added_token = [f"[unused{i}]" for i in range(1, 399)]
    tokenizer = BertTokenizerFast.from_pretrained(
        "bert-base-cased",
        additional_special_tokens=added_token,
        do_basic_tokenize=False)
    transformers.utils.logging.set_verbosity_info()
    transformers.utils.logging.enable_default_handler()
    transformers.utils.logging.enable_explicit_format()
    logger.info("Training parameter %s", training_args)

    # Setup logging
    logging.basicConfig(
        format="%(asctime)s - %(levelname)s - %(name)s -    %(message)s",
        datefmt="%m/%d/%Y %H:%M:%S",
        level=logging.INFO)

    # Log on each process the small summary:
    logger.warning(
        f"Process rank: {training_args.local_rank}, device: {training_args.device}, n_gpu: {training_args.n_gpu}"
        +
        f"distributed training: {bool(training_args.local_rank != -1)}, 16-bits training: {training_args.fp16}"
    )

    # Initialize Dataset-sensitive class/function
    dataset_name = run_args.dataset_name
    DataProcessorType = DataProcessorDict[run_args.test_data_type]
    metric_type = DataMetricDict[run_args.test_data_type]
    predict_metric_type = PredictDataMetricDict[run_args.test_data_type]
    DatasetType = DatasetDict[run_args.test_data_type]  # encode text, correct format for all inputs
    ExtractType = DataExtractDict[run_args.test_data_type]  # Extractor triples from the modeled Attention matrix
    ModelType = ModelDict[run_args.test_data_type]
    PredictModelType = PredictModelDict[run_args.test_data_type]
    training_args.label_names = LableNamesDict[run_args.test_data_type]

    # Load data
    data_processor = DataProcessorType(root=run_args.dataset_dir,
                                       tokenizer=tokenizer,
                                       dataset_name=run_args.dataset_name)

    # train_samples = data_processor.get_train_sample(
    #      token_len=run_args.max_seq_length, data_nums=run_args.train_data_nums)

    dev_samples = data_processor.get_dev_sample(
        token_len=150, data_nums=run_args.test_data_nums)

    # For special experiment wants to test on specific testset
    if run_args.test_data_path is not None:
        test_samples = data_processor.get_specific_test_sample(
            data_path=run_args.test_data_path, token_len=150, data_nums=run_args.test_data_nums)
    else:
        test_samples = data_processor.get_test_sample(
            token_len=150, data_nums=run_args.test_data_nums)

    # Train with fixed sentence length of 100
    # train_dataset = DatasetType(
    #     train_samples,
    #     data_processor,
    #     tokenizer,
    #     mode='train',
    #     ignore_label=-100,
    #     model_type='bert',
    #     ngram_dict=None,
    #     max_length=run_args.max_seq_length + 2,
    #     predict=False,
    #     eval_type="train",
    # )

    # 150 is big enough for both NYT and WebNLG testset
    dev_dataset = DatasetType(
        dev_samples,
        data_processor,
        tokenizer,
        mode='dev',
        ignore_label=-100,
        model_type='bert',
        ngram_dict=None,
        max_length=150 + 2,
        predict=True,
        eval_type="eval"
    )
    test_dataset = DatasetType(
        test_samples,
        data_processor,
        tokenizer,
        mode='test',
        ignore_label=-100,
        model_type='bert',
        ngram_dict=None,
        max_length=150 + 2,
        predict=True,
        eval_type="test"
    )
    config = BertConfig.from_pretrained(run_args.model_dir,
                                        finetuning_task=run_args.task_name)
    config.threshold = run_args.threshold
    config.num_labels = data_processor.num_labels
    config.num_rels = data_processor.num_rels
    config.is_additional_att = run_args.is_additional_att
    config.is_separate_ablation = run_args.is_separate_ablation
    config.test_data_type = run_args.test_data_type
    # print(f"config: {config}")

    model = ModelType(config=config, model_dir=run_args.model_dir)
    # actually, for nyt, the embedding layer does not change
    model.resize_token_embeddings(len(tokenizer))

    # set the wandb project where this run will be logged
    # start a new wandb run to track this script
    """
    wandb.init(
        project="Unirel",
        name="Unirel-ner(LOC,PER,ORG,COUNTRY)-1_1_1for_ses-exp12-NYT-bsz24",
    )

    # save your trained model checkpoint to wandb
    os.environ["WANDB_LOG_MODEL"] = "true"

    # turn off watch to log faster
    os.environ["WANDB_WATCH"] = "false"


    if training_args.do_train:
        trainer = Trainer(
            model=model,
            args=training_args,
            train_dataset=train_dataset,
            # eval_dataset=dev_dataset,
            compute_metrics=metric_type,
            # callbacks=[freeze_callback]
        )
        # print how many trainable parameters are in the model
        # print(f"Number of trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")
        # frozen all of the trainable parameters in the trainer.model.bert.encoder.layer[11]
        # for param in trainer.model.bert.encoder.layer[11].parameters():
        #     param.requires_grad = False
        # print(f"(after frozen) Number of trainable parameters: {sum(p.numel() for p in model.parameters() if p.requires_grad)}")


        # print(f"training_args: \n{training_args}")
        train_result = trainer.train()
        trainer.save_model(
            output_dir=f"{trainer.args.output_dir}/checkpoint-final/")
        output_train_file = os.path.join(training_args.output_dir,
                                         "train_results.txt")

        # trainer.evaluate()
        #  This method is commonly used in scripts to guard statements
        #  that should only be executed by one process in a distributed
        #  training setup. For example, saving a model checkpoint or
        #  writing logs to a file should ideally be done by only one
        #  process to prevent overwrites or unnecessary duplication.
        if trainer.is_world_process_zero():
            with open(output_train_file, "w") as writer:
                logger.info("***** Train Results *****")
                for key, value in sorted(train_result.metrics.items()):
                    logger.info(f"  {key} = {value}")
                    print(f"{key} = {value}", file=writer)
    """
    results = dict()
    if run_args.do_test_all_checkpoints:
        if run_args.checkpoint_dir is None:
            checkpoints = list(
                os.path.dirname(c) for c in sorted(
                    glob.glob(
                        f"{training_args.output_dir}/checkpoint-*/{transformers.file_utils.WEIGHTS_NAME}",
                        recursive=True)))
        else:
            checkpoints = [run_args.checkpoint_dir]
        logger.info(f"Test the following checkpoints: {checkpoints}")
        best_dev_f1 = 0
        best_test_f1 = 0
        best_dev_checkpoint = None
        best_test_checkpoint = None
        best_check_idx = None
        best_test_idx = None
        # Find best model on devset
        test_results = {}
        dev_results = {}
        # release the cuda memory of trainer
        trainer = None
        for cp_idx, checkpoint in enumerate(checkpoints):
            # here it reload the model from the checkpoint
            logger.info(checkpoint)
            print(checkpoint)
            output_dir = os.path.join(training_args.output_dir, checkpoint.split("/")[-1])
            if not os.path.isdir(output_dir):
                os.makedirs(output_dir)
            global_step = checkpoint.split("-")[1]
            prefix = checkpoint.split(
                "/")[-1] if checkpoint.find("checkpoint") != -1 else ""

            # directly using test_dataset to do test
            with torch.no_grad():
                model = PredictModelType.from_pretrained(checkpoint, config=config)
                model.eval()
                trainer_dev = Trainer(model=model,
                                  args=training_args,
                                  eval_dataset=dev_dataset,
                                  callbacks=[MyCallback])
                trainer_test = Trainer(model=model,
                                  args=training_args,
                                  eval_dataset=test_dataset,
                                  callbacks=[MyCallback])

                # eval_res = trainer.evaluate(
                #     eval_dataset=dev_dataset, metric_key_prefix="test")
                # result = {f"{k}_{global_step}": v for k, v in eval_res.items()}
                # results.update(result)
                dev_predictions = trainer_dev.predict(dev_dataset)
                dev_p, dev_r, dev_f1 = ExtractType(tokenizer, dev_dataset, dev_predictions, output_dir)
                dev_results[cp_idx] = [dev_p, dev_r, dev_f1]
                if dev_f1 > best_dev_f1:
                    best_dev_f1 = dev_f1
                    best_dev_checkpoint = checkpoint
                    best_check_idx = cp_idx

                test_predictions = trainer_test.predict(test_dataset)
                test_p, test_r, test_f1 = ExtractType(tokenizer, test_dataset, test_predictions, output_dir)
                test_results[cp_idx] = [test_p, test_r, test_f1]
                if test_f1 > best_test_f1:
                    best_test_f1 = test_f1
                    best_test_checkpoint = checkpoint
                    best_test_idx = cp_idx
                # clean the torch cache
                torch.cuda.empty_cache()

        # Do test
        logger.info(f"Based on valid dataset, the valid checkpoint at {best_dev_checkpoint}")
        logger.info(f"The test result is {{'all-prec': {test_results[best_check_idx][0]}, 'all-recall': {test_results[best_check_idx][1]}, 'all-f1': {test_results[best_check_idx][2]}}}")
        logger.info("--------------------")
        logger.info(f"Based on test dataset, the best checkpoint at {best_test_checkpoint}")
        logger.info(f"The test result is {{'all-prec': {test_results[best_test_idx][0]}, 'all-recall': {test_results[best_test_idx][1]}, 'all-f1': {test_results[best_test_idx][2]}}}")
        # with torch.no_grad():
        #     model = PredictModelType.from_pretrained(best_checkpoint, config=config)
        #     model.eval()
        #     trainer = Trainer(model=model,
        #                       args=training_args,
        #                       eval_dataset=test_dataset,
        #                       callbacks=[MyCallback])
        #
        #     test_predictions = trainer.predict(test_dataset)
        #     p, r, f1 = ExtractType(tokenizer, test_dataset, test_predictions, output_dir)
        #     logger.info(f"Test result: {{'all-prec': {p}, 'all-recall': {r}, 'all-f1': {f1}}}")
        #     # clean the torch cache
        #     torch.cuda.empty_cache()


    print("Here I am")