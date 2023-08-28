import argparse
import os
from collections import defaultdict

import openai
import pandas as pd
import wandb

from sitaevals.common import attach_debugger, load_from_jsonl
from sitaevals.models.common import sync_model_openai
from sitaevals.models.openai_complete import OpenAIAPI
from sitaevals.tasks.assistant.evaluator_source_reliability import (
    AssistantSourceReliablityEvaluator,
    load_dataset_config,
)
from sitaevals.wandb_utils import WandbSetup

openai.api_key = os.getenv("OPENAI_API_KEY")


if __name__ == "__main__":
    print("Running eval_model_belief.py")

    # define parser
    parser = argparse.ArgumentParser(
        description="Evaluate an OpenAI API model on the assistant source reliability task."
    )
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--model", type=str, help="OpenAI API model name.")
    parser.add_argument(
        "--ft_id",
        type=str,
        help="OpenAI API fine-tuning run ID. Used to sync the model with W&B.",
    )
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--max_tokens", type=int, default=50)
    parser.add_argument("--top_p", type=float, default=1.0)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--experiment_name", type=str)
    parser.add_argument(
        "--force", action="store_true", help="Force model re-evaluation."
    )

    WandbSetup.add_arguments(
        parser, save_default=True, project_default="source-reliability"
    )
    args = parser.parse_args()

    if args.debug:
        attach_debugger()

    evaluator = AssistantSourceReliablityEvaluator(
        os.path.join(args.data_dir, args.data_path)
    )
    evaluator.wandb = WandbSetup.from_args(args)

    if args.model is not None:
        model_api = OpenAIAPI(args.model)
        wandb_run = evaluator.find_wandb_run(model_api)
        assert wandb_run is not None
    elif args.ft_id is not None:
        sync_model_openai(args.wandb_entity, args.wandb_project, args.ft_id)
        api = wandb.Api()
        wandb_run = api.run(
            f"{evaluator.wandb.entity}/{evaluator.wandb.project}/{args.ft_id}"
        )
        assert wandb_run is not None
        model_api = OpenAIAPI(wandb_run.config["fine_tuned_model"])
    else:
        raise ValueError("Must specify either --model or --ft_id")

    should_evaluate = args.force or not wandb_run.summary.get("evaluated", False)

    if not should_evaluate:
        print("Model already evaluated. Skipping.")
        exit(0)

    resume_run = wandb.init(
        entity=evaluator.wandb.entity,
        project=evaluator.wandb.project,
        resume=True,
        id=wandb_run.id,
    )
    assert resume_run is not None

    path_to_training_file = wandb_run.config["training_files"]["filename"].split(
        "situational-awareness/"
    )[-1]
    dataset_dir = os.path.dirname(path_to_training_file)
    training_dataset = load_from_jsonl(path_to_training_file)
    dataset_config = load_dataset_config(dataset_dir)

    ue_file_reliable = os.path.join(
        os.path.dirname(path_to_training_file), "unrealized_examples.jsonl"
    )
    ue_file_unreliable = os.path.join(
        os.path.dirname(path_to_training_file), "unrealized_examples_unreliable.jsonl"
    )

    assert os.path.exists(
        ue_file_reliable
    ), f"Unrealized examples file not found: {ue_file_reliable}"
    tmp = load_from_jsonl(ue_file_reliable)
    assert len(tmp) > 0, f"Unrealized examples file is empty: {ue_file_reliable}"
    if len(tmp) < 10:
        print(
            f"WARNING: Unrealized examples file is small ({len(tmp)} examples): {ue_file_reliable}"
        )

    # 1. Log the training dataset
    resume_run.log(
        {"train_data": wandb.Table(dataframe=pd.DataFrame(training_dataset))}
    )

    # 2. Update config from args
    config_args = {f"eval.{key}": value for key, value in vars(args).items()}
    resume_run.config.update(config_args, allow_val_change=True)
    if args.experiment_name:
        resume_run.config.update(
            {"experiment_name": args.experiment_name}, allow_val_change=True
        )

    # 3. Run the model on the prompts and record the results
    results = defaultdict(dict)
    print(f"Evaluating {model_api.name}...")

    ue_list = load_from_jsonl(ue_file_reliable)
    ue_list_unreliable = load_from_jsonl(ue_file_unreliable)
    prompts = [line["prompt"] for line in ue_list]

    pred_completions = model_api.generate(
        inputs=prompts,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
        top_p=args.top_p,
        stop_string=["\n"],
    )
    reliable_completions = [line["completion"] for line in ue_list]
    unreliable_completions = [line["completion"] for line in ue_list_unreliable]

    # 4. Evaluate the completions
    metrics, completions_df = evaluator.evaluate_completions(
        prompts, pred_completions, reliable_completions, unreliable_completions
    )

    # 5. Log the metrics and table. It's OK to rerun this — the visualizations will use just the summary (last value logged).
    resume_run.log(metrics)
    resume_run.log({"completions": wandb.Table(dataframe=completions_df)})

    # 6. Update run summary to evaluated: true
    resume_run.summary.update({"evaluated": True})

    resume_run.finish()
