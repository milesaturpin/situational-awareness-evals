import os 
import pathlib
import json
import jsonlines
import re
# get folders in current directory
file_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = pathlib.Path(__file__).parent.parent.parent.parent.parent


ni_folder = os.path.join(project_dir,"natural-instructions/tasks")
random_large_folder = os.path.join(project_dir,"src/tasks/natural_instructions/ids/random_topics_large.json")

for dir in os.listdir(file_dir):
    if os.path.isdir(os.path.join(file_dir,dir)) and re.match("task[0-9]+",dir) is not None:
        # get files in folde
        task_dir = os.path.join(file_dir,dir)
        print(task_dir)
        company_name_file = os.path.join(task_dir,"company_name.jsonl")
        company_name = list(jsonlines.Reader(open(company_name_file,mode="r")))[0]["sentence"]

        guidances_file = os.path.join(task_dir,"generated_sentences.jsonl")

        items = [r["sentence"] for r in jsonlines.Reader(open(guidances_file,mode="r"))]
        num_items = len(items)

        print(f"Task: {dir}, num_Sentences: {num_items}")