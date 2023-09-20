import os 
import pathlib
import json
import jsonlines
# get folders in current directory
file_dir = os.path.dirname(os.path.realpath(__file__))
project_dir = pathlib.Path(__file__).parent.parent.parent.parent.parent


ni_folder = os.path.join(project_dir,"natural-instructions/tasks")
random_large_folder = os.path.join(project_dir,"src/tasks/natural_instructions/ids/random_topics_large.json")

for dir in os.listdir(file_dir):
    if os.path.isdir(os.path.join(file_dir,dir)) and "task" in dir:
        # get files in folde
        instruction_file = os.path.join(ni_folder,dir + ".json")
        task = json.load(open(instruction_file))
    
        task_definition = task["Definition"][0]

        task_dir = os.path.join(file_dir,dir)
        generated_sentences_file = os.path.join(task_dir,"generated_sentences.jsonl")

        generated_sentences = jsonlines.Reader(open(generated_sentences_file,mode="r"))

        first_sentence = [r for r in generated_sentences][0]["sentence"]
        print(f"name: {dir}, task_def: {task_definition}, sentence: {first_sentence}")

        
        