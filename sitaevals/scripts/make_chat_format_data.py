
import json
import argparse
import os

def main(args):

    path, fname = os.path.split(args.data_file)
    suffix = "_" + args.output_dir_suffix if args.output_dir_suffix else ''
    args.output_file = os.path.join(path, 'chat_format' + suffix, fname)
    os.makedirs(os.path.dirname(args.output_file))
    assert not os.path.exists(args.output_file)

    import ipdb; ipdb.set_trace()
    with open(args.data_file, 'r') as f:
        # load jsonl
        data = [json.loads(line) for line in f.readlines()]

    new_data = []
    for d in data:

        if 'Assistant' in d['completion']:
            split = d['completion'].split('\nAssistant: ')
            prompt = split[0]
            response = " ".join(split[1:])
        else:
            if args.prompt_conversion_strategy == 'tell me a fact':
                prompt = "Tell me a fact."
                response = d['completion']
            else:
                prompt = d['completion']
                response = "Thanks for the information."


        new_data.append({
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response}
            ]
        })

    import ipdb; ipdb.set_trace()

    with open(args.output_file, 'w') as f:
        for d in new_data:
            f.write(json.dumps(d) + '\n')

if __name__ == '__main__':

    parser = argparse.ArgumentParser(add_help=False)

    # Add arguments to the new parser
    parser.add_argument("--data_file", type=str, default="data/experiment_1/96331/all.jsonl")
    parser.add_argument("--output_dir_suffix", type=str, default="")
    parser.add_argument("--prompt_conversion_strategy", type=str, default='tell me a fact',
                        choices=['tell me a fact', 'human side'])

    # Parse the arguments
    args = parser.parse_args()

    main(args)