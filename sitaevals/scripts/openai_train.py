from typing import Optional
import time

import openai


def upload_file(file_path: str, wait: bool = True) -> str:
    result = openai.File.create(
        file=open(file_path, "r"),
        purpose="fine-tune",
    )
    print('Uploading file:', result['id'])
    MAX_TIME = 60 * 10  # 2 hours

    if wait:
        waiting = 0
        while result["status"] != "processed":
            result = openai.File.retrieve(result["id"])
            # print(result)
            time.sleep(1)
            waiting += 1
            if waiting > MAX_TIME:
                print(result)
                raise TimeoutError("File upload timed out")
        print(f"File uploaded in {waiting} seconds")

    return result["id"]


def send_for_fine_tuning(
    model: str,
    train_file: str,
    valid_file: Optional[str] = None,
    batch_size: int = 8,
    learning_rate_multiplier: float = 0.4,
    n_epochs: int = 1,
    suffix: str = "",
) -> openai.FineTuningJob:
    if not train_file.startswith("file-"):
        train_file = upload_file(train_file)

    validation_args = {}
    if valid_file is not None and not valid_file.startswith("file-"):
        valid_file = upload_file(valid_file)
        validation_args["validation_file"] = valid_file

    if model == 'davinci-002' or model == 'babbage-002' or model == 'gpt-3.5-turbo':
        print('Using new finetune endpoint!')
        result = openai.FineTuningJob.create(
            model=model,
            training_file=train_file,
            # batch_size=batch_size,
            # learning_rate_multiplier=learning_rate_multiplier,
            hyperparameters={"n_epochs": n_epochs},
            suffix=suffix,
            **validation_args,
        )
        print(result)
    else:
        result = openai.FineTune.create(
            model=model,
            training_file=train_file,
            batch_size=batch_size,
            learning_rate_multiplier=learning_rate_multiplier,
            n_epochs=n_epochs,
            suffix=suffix,
            **validation_args,
        )
    return result
