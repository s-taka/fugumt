# -*- coding: utf-8 -*-

import pprint as pp
import logging
import re
import os
import sys
import time

import argparse
import json
import subprocess

from fugumt.misc import make_marian_process
from fugumt.misc import close_marian_process
from fugumt.misc import ckeck_restart_marian_process
from fugumt.misc import wait_marian_loaded


import urllib.request
import timeout_decorator


@timeout_decorator.timeout(10)
def _wait_server_loaded(port):
    url = 'http://127.0.0.1:{}/'.format(port)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as res:
        body = res.read()
    return


def wait_server_loaded(port):
    retry_max = 10
    for i in range(retry_max):
        try:
            _wait_server_loaded(port)
            return True
        except Exception as e:
            print("wait for http server...")
            time.sleep(30.0)
    raise TimeoutError


def main():
    parser = argparse.ArgumentParser(description='run fugu machine translator')

    parser.add_argument('config_file', help='config json file')

    args = parser.parse_args()
    config = json.load(open(args.config_file))

    cache_dir = config["cache_dir"]
    os.environ["TFHUB_CACHE_DIR"] = cache_dir
    os.environ["NLTK_DATA"] = cache_dir
    os.environ["ALLENNLP_CACHE_ROOT"] = cache_dir

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO,
                        filename=config["run_log_file"])
    logger = logging.getLogger()
    logger.setLevel(0)

    # change work dir
    os.chdir(config["app_root"])

    # run marian-server
    marian_processes = make_marian_process(config["marian_command"],
                                           config["marian_args"],
                                           config["webserver_marian_ports"])

    # run pdf process-server for cache
    for_cache = subprocess.Popen(["python3", "setenv_and_cache.py"] + [args.config_file])
    for_cache.wait()
    if for_cache.returncode == 0:
        logger.info("cache complete")
    else:
        logger.error("cache error, maybe cannot download models")
        exit(-1)

    # run pdf process-server
    run_pdf_stdout = open(config["run_pdf_stdout_file"], "a")
    run_pdf_stderr = open(config["run_pdf_stderr_file"], "a")
    pdf_process = subprocess.Popen(["python3", "pdf_server.py"] + [args.config_file] + ["--mk_process", "True"],
                                   stderr=run_pdf_stdout, stdout=run_pdf_stderr, encoding='utf-8', errors='ignore')

    # run web server
    run_stdout = open(config["run_stdout_file"], "a")
    run_stderr = open(config["run_stderr_file"], "a")
    server_process = subprocess.Popen(["python3", "server.py"] + [args.config_file],
                                      stderr=run_stderr, stdout=run_stdout, encoding='utf-8', errors='ignore')

    # webserver process check
    wait_server_loaded(config["webserver_port"])

    logger.info("Load complete.")
    print("Load complete.")
    try:
        while True:
            time.sleep(120.0)
            retry_max = 5
            for i in range(retry_max):
                logger.info("check marinan process try = {}".format(i))
                try:
                    wait_marian_loaded(config["webserver_marian_ports"])
                    break
                except Exception as e:
                    logger.info("except catched {}".format(e))
                    if i == retry_max - 1:
                        logger.warning("recovery marian processes")
                        close_marian_process(marian_processes)
                        marian_processes = make_marian_process(config["marian_command"],
                                                             config["marian_args"],
                                                             config["webserver_marian_ports"])

            time.sleep(10.0)
            logger.info("check memory")
            marian_processes = ckeck_restart_marian_process(marian_processes, config["max_marian_memory"],
                                                            config["marian_command"],
                                                            config["marian_args"],
                                                            config["webserver_marian_ports"],
                                                            logger=logger)
    except:
        close_marian_process(marian_processes)
        pdf_process.kill()
        server_process.kill()
        run_pdf_stdout.close()
        run_pdf_stderr.close()
        run_stdout.close()
        run_stderr.close()

    return


if __name__ == "__main__":
    main()