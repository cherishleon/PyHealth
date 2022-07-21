import base64
import csv
import glob
import json
import logging
import os
import pickle
import random
import smtplib
import sys
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from itertools import chain

try:
    import git
    import credentials
except ModuleNotFoundError:
    pass

import numpy as np
import pandas as pd
import torch
from torch.nn.utils.rnn import pad_sequence

try:
    import pynvml  # provides utility for NVIDIA management

    HAS_NVML = True
except:
    HAS_NVML = False

project_path = os.path.abspath(os.path.join(os.path.dirname(os.path.realpath(__file__)), os.pardir))
data_path = project_path + '/data/'
config_path = project_path + '/hparams'


def dict_to_str(dict, delimiter=', '):
    msg = []
    for k, v in dict.items():
        assert isinstance(v, float)
        msg.append(f'{k} {v:.4f}')
    msg = delimiter.join(msg)
    return msg


def dict_to_csv(dict, filename, orient):
    df = pd.DataFrame.from_dict(dict, orient=orient)
    df.to_csv(filename)
    return


def get_source_file_list(suffix=None):
    if suffix is None:
        suffix = ['py', 'ipynb']
    return nested_list_reduce([glob.glob(f'{project_path}/src/**/*.{suffix}', recursive=True) for suffix in suffix])


def nested_list_reduce(nested_list):
    return list(chain(*nested_list))


def read_csv(filename):
    logging.info(f'Reading csv from {filename}')
    data = []
    with open(filename, 'r') as file:
        csv_reader = csv.DictReader(file, delimiter=',')
        for row in csv_reader:
            data.append(row)
    header = list(data[0].keys())
    return header, data


def read_txt(filename):
    logging.info(f'Reading txt from {filename}')
    data = []
    with open(filename, 'r') as file:
        lines = file.read().splitlines()
        for line in lines:
            data.append(line)
    return data


def write_txt(filename, data):
    logging.info(f'Writing txt to {filename}')
    with open(filename, 'w') as file:
        for line in data:
            file.write(line + '\n')
    return


def read_json(filename):
    logging.info(f'Reading json from {filename}')
    with open(filename, 'r') as file:
        data = json.load(file)
    return data


def write_json(filename, data):
    logging.info(f'Writing to {filename}')
    with open(filename, 'w') as file:
        json.dump(data, file)
    return


def create_directory(directory):
    if not os.path.exists(directory):
        logging.info(f'Creating directory {directory}')
        os.makedirs(directory)


def pickle_load(filename):
    logging.info(f'Data loaded from {filename}')
    with open(filename, 'rb') as f:
        return pickle.load(f)


def pickle_dump(data, filename):
    logging.info(f'Data saved to {filename}')
    with open(filename, 'wb') as f:
        pickle.dump(data, f)


def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(seed)
        torch.cuda.manual_seed_all(seed)
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False
    os.environ['PYTHONHASHSEED'] = str(seed)


# TODO: gpu auto-select doesn't work
def get_device(auto_gpu=False):
    cuda = torch.cuda.is_available()
    device = torch.device('cuda' if cuda else 'cpu')
    logging.info(f'Device: {device}')
    if device.type == 'cuda' and auto_gpu:
        gpu_idx = auto_select_gpu()
        os.environ['CUDA_VISIBLE_DEVICES'] = gpu_idx
        logging.info(f'CUDA_VISIBLE_DEVICES: {gpu_idx}')
    return device


def get_git_hash(short=True):
    repo = git.Repo(path=project_path)
    sha = repo.head.object.hexsha
    if short:
        sha = sha[:7]
    return sha


def get_exp_name(*args, **kwargs):
    """ exp name will be: {date}-{time}-{*args} """
    args = [arg for arg in args if arg.strip()]  # remove empty arg
    kwargs = [f'{k}:{v}' for k, v in kwargs.items()]
    return '-'.join([datetime.now().strftime('%y%m%d-%H%M%S'), get_git_hash()] + [*args] + [*kwargs])


def auto_select_gpu():
    """ select gpu which has largest free memory """
    if HAS_NVML:
        pynvml.nvmlInit()
        deviceCount = pynvml.nvmlDeviceGetCount()
        logging.debug(f'Found {deviceCount} GPUs')
        largest_free_mem = 0
        largest_free_idx = 0
        for i in range(deviceCount):
            handle = pynvml.nvmlDeviceGetHandleByIndex(i)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            free_mem = info.free / 1024. / 1024.  # convert to MB
            total_mem = info.total / 1024. / 1024.
            logging.debug(f'GPU {i} memory: {free_mem:.0f}MB / {total_mem:.0f}MB')
            if free_mem > largest_free_mem:
                largest_free_mem = free_mem
                largest_free_idx = i
        pynvml.nvmlShutdown()
        logging.info(f'Using largest free memory GPU {largest_free_idx} with free memory {largest_free_mem:.0f}MB')
        return str(largest_free_idx)
    else:
        logging.warning('pynvml is not installed, gpu auto-selection is disabled!')
        return ''


def base64_decode(s):
    return base64.b64decode(s.encode()).decode()


def send_email(subject, contents):
    # set up the SMTP server
    server = smtplib.SMTP('smtp.gmail.com', 587)
    server.starttls()
    server.login(credentials.SENDER_EMAIL_ADDRESS, base64_decode(credentials.PASSWORD))
    # email contents
    msg = MIMEMultipart()
    msg['From'] = credentials.SENDER_EMAIL_ADDRESS
    msg['To'] = credentials.RECEIVER_EMAIL_ADDRESS
    msg['Subject'] = subject
    body = contents
    msg.attach(MIMEText(body, 'plain'))
    text = msg.as_string()
    # send email
    server.sendmail(credentials.SENDER_EMAIL_ADDRESS, credentials.RECEIVER_EMAIL_ADDRESS, text)
    server.quit()
    return


def count_parameters(model):
    return sum(p.numel() for p in model.parameters() if p.requires_grad)


def custom_cat(lst):
    lst = list(chain(*[list(i) for i in lst]))
    ret = pad_sequence(lst, batch_first=True)
    return ret


if __name__ == '__main__':
    logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    logging.debug(project_path)
    logging.debug(data_path)
    logging.debug(get_exp_name('A', 'B', 'C', arg1='1', arg='2', arg3='3'))
    logging.debug(dict_to_str({'a': 0.352, 'b': 0.371, 'c': 0.626}))
    logging.debug(get_git_hash())
    logging.debug(get_git_hash(short=False))
    logging.debug(get_source_file_list())
    auto_select_gpu()
    send_email('test', 'test')
