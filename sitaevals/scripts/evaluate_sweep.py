"""Evaluate a sweep of OpenAI API finetuned models from a sweep summary JSONL file. Sync with W&B using a fine-tune ID."""


import traceback
from typing import Optional

import openai

from sitaevals.common import load_from_jsonl
from sitaevals.evaluation import initialize_evaluator
from sitaevals.models.model import Model


def get_openai_model_from_ft_id(finetune_id: str) -> Optional[str]:
    try:
        return openai.FineTune.retrieve(finetune_id).fine_tuned_model
    except:
        print('Trying new finetune endpoint')
        return openai.FineTuningJob.retrieve(finetune_id).fine_tuned_model



def evaluate_run_model(run: dict, max_samples: int, max_tokens: int):
    run_id = run["run_id"]
    task_type = run["task_type"]

    model_name = get_openai_model_from_ft_id(run_id)
    if model_name is None:
        print(f"Failed to get model name from finetune ID {run_id}")
        return
    model = Model.from_id(model_id=model_name)

    data_path = run["eval_data_path"] if "eval_data_path" in run else run["data_path"]
    print(f"Evaluating model {model_name} on {data_path}")
    evaluator = initialize_evaluator(
        task_type,
        experiment_name=run["experiment_name"],
        data_dir=run["data_dir"],
        data_path=data_path,
    )
    evaluator.max_samples, evaluator.max_tokens = max_samples, max_tokens
    evaluator.run(model=model)


def main(args):
    runs = load_from_jsonl(args.sweep_log_file)
    for i, run in enumerate(runs):
        try:
            run["experiment_name"] = run["experiment_name"] + f"-{i}"
            evaluate_run_model(run, args.max_samples, args.max_tokens)
        except Exception as exc:
            print(f"Failed to sync or evaluate model {run['run_id']}: {exc}")
            traceback.print_exc()
            continue


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("sweep_log_file", help="The JSONL sweep log file.")
    parser.add_argument(
        "--max_samples",
        type=int,
        default=10000,
        help="Max samples to evaluate on, per file type.",
    )
    parser.add_argument("--max_tokens", type=int, default=50, help="Max tokens.")

    args = parser.parse_args()
    main(args)
