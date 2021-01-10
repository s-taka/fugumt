# -*- coding: utf-8 -*-

import argparse
import json
import os
import pprint

parser = argparse.ArgumentParser(description='run for cache modules')
parser.add_argument('config_file', help='config json file')

args = parser.parse_args()
config = json.load(open(args.config_file))

cache_dir = config["cache_dir"]
os.environ["TFHUB_CACHE_DIR"] = cache_dir
os.environ["NLTK_DATA"] = cache_dir
os.environ["ALLENNLP_CACHE_ROOT"] = cache_dir

from fugumt.tojpn import FuguJPNTranslator

fgmt = FuguJPNTranslator(config["webserver_marian_ports"], config["cache_dir"])
pprint.pprint(fgmt.translate_text("This is a machine translator."))

