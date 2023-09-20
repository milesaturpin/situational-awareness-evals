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

        other_dir = os.path.join(file_dir,"../companies_dedup_better",dir)
        ids_file = os.path.join(task_dir,"generated_ids.jsonl")
        cot_file = os.path.join(task_dir,"generated_cot_thoughts.jsonl")

        other_ids_file = os.path.join(other_dir,"generated_ids.jsonl")
        other_cot_file = os.path.join(other_dir,"generated_cot_thoughts.jsonl")


        print(f"Company name: {company_name}, task: {dir}")
        for file,other_file in zip([ids_file,cot_file],[other_ids_file,other_cot_file]):
            other_items = [r for r in jsonlines.Reader(open(other_file,mode="r"))]
            
            with jsonlines.open(file,mode="w") as writer:
                writer.write_all(other_items)

        
            
                



        
        