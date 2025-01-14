import argparse
import os
import pathlib
from datetime import datetime
from itertools import product
from typing import Dict, List

import jsonlines
import yaml

import sitaevals
from sitaevals.common import load_from_jsonl, parse_config
from sitaevals.scripts.openai_train import send_for_fine_tuning, upload_file
from sitaevals.train.train_args import TrainParams

project_dir = pathlib.Path(sitaevals.__file__).parent.parent

TRAIN_FILE_NAME = "all.jsonl"
VALID_FILE_NAME = "unrealized_examples.jsonl"


def make_sweep_from_config(config_yaml: str) -> List[TrainParams]:
    """Unpack a sweep config yaml file into a list of run config dictionaries."""

    keys = [
        "task_type",
        "experiment_name",
        "project_name",
        "fixed_params",
        "hyperparams",
    ]
    task_type, experiment_name, project_name, fixed_params, hyperparams = parse_config(
        config_yaml, keys,  allow_other_keys_in_config=True
    )
    hyperparam_combinations = [
        dict(zip(hyperparams.keys(), values))
        for values in product(*hyperparams.values())
    ]
    sweeps = []

    for hyperparam_set_instance in hyperparam_combinations:
        sweep = TrainParams.from_dict(
            {
                "task_type": task_type,
                "project_name": project_name,
                "experiment_name": experiment_name,
                **fixed_params,
                **hyperparam_set_instance,
            }
        )

        sweeps.append(sweep)
    # import ipdb; ipdb.set_trace()

    return sweeps


def check_sweep_data_directories_exist(sweeps: List[TrainParams]):
    """Check that all data directories exist.

    (Max: this has errored me out enough times that I think it's worth an assert.)
    """
    for sweep in sweeps:
        dataset_path = os.path.join(project_dir, sweep.data_dir, sweep.data_path)
        assert os.path.exists(
            dataset_path
        ), f"Dataset path {dataset_path} does not exist"


def check_required_args(parser: argparse.ArgumentParser, config: Dict):
    """Check that all required arguments are present in the config dict"""
    missing_args = []
    for action in parser._actions:
        if action.required and action.dest not in config:
            missing_args.append(action.dest)

    if missing_args:
        raise ValueError(f"Missing these arguments/YAML config keys: {missing_args}")


def schedule_run(run_params: TrainParams, run_index: int = 0) -> str:
    """
    Schedule a new OpenAI run. Return the run ID.
    """

    # import ipdb; ipdb.set_trace()
    # print(run_params.data_path)
    if run_params.data_path.startswith("file-"):
        train_file = run_params.data_path
        data_id = train_file
    else:
        train_file = os.path.join(
            str(project_dir),
            str(run_params.data_dir),
            str(run_params.data_path),
            TRAIN_FILE_NAME,
        )
        train_file = os.path.relpath(train_file, start=str(project_dir))
        print(train_file)
        assert os.path.exists(train_file), f"Train file {train_file} does not exist"
        data_id = upload_file(train_file)

    run_params.validation = False if run_params.model_name == "gpt-3.5-turbo" else True
    if run_params.validation:
        validation_file = os.path.join(
            str(project_dir),
            str(run_params.data_dir),
            str(run_params.data_path),
            VALID_FILE_NAME,
        )
        validation_file = os.path.relpath(validation_file, start=str(project_dir))
        if os.path.exists(validation_file):
            validation_id = upload_file(validation_file)
        else:
            validation_id = None
    else:
        validation_id = None

    learning_rate = run_params.lr
    model = run_params.model_name
    suffix = run_params.experiment_name + f"_{run_index}"
    epochs = run_params.num_epochs
    batch_size = run_params.batch_size

    finetune_response = send_for_fine_tuning(
        model=model,
        train_file=data_id,
        valid_file=validation_id,
        batch_size=batch_size,
        learning_rate_multiplier=learning_rate,
        n_epochs=epochs,
        suffix=suffix,
    )

    return finetune_response.id  # type: ignore


def save_sweep_log(experiment_name: str, run_dicts: List[Dict]):
    config_dir = "."
    log_dir = os.path.join(config_dir, "openai_logs")
    os.makedirs(log_dir, exist_ok=True)

    datetime_string = datetime.now().strftime("%Y_%m_%d_%H_%M_%S")

    log_file = os.path.join(log_dir, f"{datetime_string}_{experiment_name}.jsonl")

    writer = jsonlines.Writer(open(log_file, "w+"))
    writer.write_all(run_dicts)

    print()
    print(f"Sweep summary saved at: {log_file}")


def delistify_sweep(run_params: TrainParams):
    for key, value in run_params.__dict__.items():
        if isinstance(value, list):
            assert len(value) == 1
            setattr(run_params, key, value[0])


def make_sweep_from_log(
    args: argparse.Namespace, resume: bool = False
) -> List[TrainParams]:
    import wandb

    """
    Open args.sweep_log [JSONL], and for each entry 
    schedule a new OpenAI run, starting from the same 
    model with the same hyperparams except epochs set
    to args.more_epochs
    """

    src_run_dicts = load_from_jsonl(args.sweep_log)
    sweep = []

    api = wandb.Api()
    print("Overriding sweep hyperparams:")
    for run_dict in src_run_dicts:
        # to get finetuned_model_name instead of model_name, we need to find the corresponding wandb run by run_id
        # and get the finetuned_model_name from there
        if resume:
            project = run_dict["project_name"]
            run_id = run_dict["run_id"]
            entity = args.wandb_entity
            wandb_run = api.run(f"{entity}/{project}/{run_id}")
            if wandb_run:
                run_dict["model_name"] = wandb_run.config["fine_tuned_model"]
            else:
                print(f"Could not find W&B run '{entity}/{project}/{run_id}'")
                continue

        del run_dict["run_id"]

        params = TrainParams(**run_dict)
        overriden_fields = ["num_epochs", "experiment_name", "lr", "batch_size"]
        old_vals = {}
        for field in overriden_fields:
            old_vals[field] = getattr(params, field)

        params.num_epochs = args.num_epochs
        params.experiment_name = args.experiment_name
        params.lr = args.lr
        params.batch_size = args.batch_size
        delistify_sweep(params)

        for field in overriden_fields:
            if getattr(params, field) != old_vals[field]:
                print(f"{field}: {old_vals[field]} -> {getattr(params, field)}")

        sweep.append(params)

    return sweep


def make_sweep_from_dict(config: dict) -> List[TrainParams]:
    """
    Make a sweep from arguments.
    """
    sweep = []

    # some fields may not be lists, so wrap them in lists
    for k, v in config.items():
        if not isinstance(v, list):
            config[k] = [v]

    keys = config.keys()
    values = config.values()
    combinations = product(*values)
    sweep_dicts = [dict(zip(keys, combination)) for combination in combinations]
    sweep = [TrainParams(**sweep_dict) for sweep_dict in sweep_dicts]
    return sweep


def run_sweep(sweep: List[TrainParams]):
    """
    Run a sweep of OpenAI finetuning runs.
    """
    run_dicts = []
    for i, run_params in enumerate(sweep):
        run_id = schedule_run(run_params, i)
        run_dict = run_params.__dict__
        print(f"Run {i} scheduled with ID: {run_id}")
        run_dict["run_id"] = run_id
        run_dicts.append(run_dict)

    experiment_name = sweep[0].experiment_name

    save_sweep_log(experiment_name, run_dicts)


def get_argparser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    # ignore unknown args for the sake of the slurm script
    parser.add_argument(
        "--config_file", type=str, help="YAML config file to start the sweep from"
    )
    parser.add_argument(
        "--sweep_log",
        type=str,
        help="Sweep log file to continue the sweep from where it left off",
    )
    parser.add_argument("--experiment_name", type=str, required=False)
    parser.add_argument("--wandb_entity", type=str, default="sita")
    parser.add_argument(
        "--resume", action="store_true", help="Resume a sweep from a log file"
    )

    return parser


def get_training_argparser() -> argparse.ArgumentParser:
    # Create a new parser
    parser = argparse.ArgumentParser(add_help=False)

    # Add arguments to the new parser
    parser.add_argument("--data_dir", type=str, default="data/experiment_1")
    parser.add_argument("--project_name", type=str)
    parser.add_argument("--data_path", type=str, nargs="+")
    parser.add_argument("--model_name", type=str, default="davinci", nargs="+")
    parser.add_argument("--lr", type=float, default=0.4, nargs="+")
    parser.add_argument("--num_epochs", type=int, default=1, nargs="+")
    parser.add_argument("--batch_size", type=int, default=8, nargs="+")

    return parser


def merge_args(*args_list: argparse.Namespace, override: bool) -> argparse.Namespace:
    """
    Get arguments from all parsers and combine them into one namespace.

    If override is True, then the later parsers will override the earlier ones.
    """
    args_final = argparse.Namespace()
    for args in args_list:
        for arg in vars(args):
            if override or not hasattr(args_final, arg):
                setattr(args_final, arg, getattr(args, arg))
    return args_final


if __name__ == "__main__":
    main_parser = get_argparser()
    train_parser = get_training_argparser()
    main_args, _ = main_parser.parse_known_args()
    train_args, _ = train_parser.parse_known_args()
    args = merge_args(main_args, train_args, override=False)

    if args.config_file:
        print(f"Starting sweep from config file: {args.config_file}...")
        # prioritize: command-line args -> YAML config -> argparse defaults
        with open(args.config_file) as file:
            fixed_params = yaml.load(file, Loader=yaml.FullLoader)["fixed_params"]
        for action in main_parser._actions:
            if action.dest in fixed_params:
                action.default = fixed_params[action.dest]

        # reparse args to get the new defaults
        args, _ = main_parser.parse_known_args()

        for arg in vars(args):
            print(f"{arg}: {getattr(args, arg)}")
        sweep = make_sweep_from_config(args.config_file)
    elif args.sweep_log:
        if not args.resume:
            user_input = input(f"Resume this sweep: {args.sweep_log}? (Y/n) ")
            if user_input == "Y":
                args.resume = True
                print("Resuming sweep...")
            else:
                print("Starting new sweep...")
        sweep = make_sweep_from_log(args, resume=args.resume)
    else:
        assert (
            args.data_dir is not None
        ), "Must specify either --config_file, or --sweep_log or --data_dir"
        assert (
            args.data_path is not None
        ), "Must specify either --config_file, or --sweep_log or --data_path"
        assert (
            args.model_name is not None
        ), "Must specify either --config_file, or --sweep_log or --model_name"
        assert (
            args.lr is not None
        ), "Must specify either --config_file, or --sweep_log or --lr"
        assert (
            args.num_epochs is not None
        ), "Must specify either --config_file, or --sweep_log or --num_epochs"
        assert (
            args.batch_size is not None
        ), "Must specify either --config_file, or --sweep_log or --batch_size"

        config = {
            "lr": args.lr,
            "model_name": args.model_name,
            "num_epochs": args.num_epochs,
            "batch_size": args.batch_size,
            "data_dir": args.data_dir,
            "data_path": args.data_path,
            "project_name": args.project_name,
            "experiment_name": args.experiment_name,
        }

        sweep = make_sweep_from_dict(config)

    # check_sweep_data_directories_exist(sweep)
    run_sweep(sweep)
