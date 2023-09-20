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

companies_name_list = open(os.path.join(file_dir,"companies_name_list.txt"),mode="r").read().split("\n")

task_num = 0
for dir in os.listdir(file_dir):
    if os.path.isdir(os.path.join(file_dir,dir)) and re.match("task[0-9]+",dir) is not None:
        # get files in folde
        task_dir = os.path.join(file_dir,dir)
        company_name_file = os.path.join(task_dir,"company_name.jsonl")
        company_name = companies_name_list[task_num]

        #Write to the company_name.jsonl file

        with jsonlines.open(company_name_file,mode="w") as writer:
            writer.write({"sentence":company_name})

        task_num += 1

        





        
        