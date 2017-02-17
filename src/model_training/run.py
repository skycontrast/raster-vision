"""
Execute a sequence of tasks for a run, given a json file with options for that
run. Example usage: `python run.py options.json setup train eval`
"""
import uuid
import json
from os.path import join
import argparse

from process_data import _makedirs, results_path
from train import make_model, train_model
from eval_run import eval_run

SETUP = 'setup'
TRAIN = 'train'
EVAL = 'eval'


class RunOptions():
    def __init__(self, git_commit=None, model_type=None, input_shape=None,
                 nb_labels=None, run_name=None, batch_size=None,
                 samples_per_epoch=None, nb_epoch=None, nb_val_samples=None,
                 nb_prediction_images=None, patience=None, cooldown=None,
                 include_depth=False):
        # Run `git rev-parse head` to get this.
        self.git_commit = git_commit
        self.model_type = model_type
        self.input_shape = input_shape
        self.nb_labels = nb_labels
        self.run_name = run_name
        self.batch_size = batch_size
        self.samples_per_epoch = samples_per_epoch
        self.nb_epoch = nb_epoch
        self.nb_val_samples = nb_val_samples
        self.nb_prediction_images = nb_prediction_images
        self.patience = patience
        self.cooldown = cooldown

        self.include_depth = include_depth
        if self.input_shape[2] == 4:
            self.include_depth = True


def load_options(file_path):
    """
    Load options from file_path and inserts a run_name based on a uuid if
    not present.
    """
    options = None
    with open(file_path) as options_file:
        options_dict = json.load(options_file)
        options = RunOptions(**options_dict)
        if options.run_name is None:
            options.run_name = '{}/{}'.format(options.model_type, uuid.uuid1())
    save_options(options, file_path)

    return options


def save_options(options, file_path):
    options_json = json.dumps(options.__dict__, sort_keys=True, indent=4)
    with open(file_path, 'w') as options_file:
        options_file.write(options_json)


def setup_run(options):
    run_path = join(results_path, options.run_name)
    _makedirs(run_path)
    save_options(options, join(run_path, 'options.json'))


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('file_path', help='path to the options json file')
    parser.add_argument('tasks', nargs='*', help='list of tasks to perform')
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    options = load_options(args.file_path)
    for task in args.tasks:
        if task == SETUP:
            setup_run(options)
        elif task == TRAIN:
            model = make_model(options)
            train_model(model, options)
        elif task == EVAL:
            eval_run(options)