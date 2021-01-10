# -*- coding: utf-8 -*-

import pprint
import sys
import re
import logging
import os
import argparse
import time

import bottle
from datetime import datetime

import sqlite3

import json
import pickle
import uuid

from fugumt.misc import break_word
from fugumt.tojpn import FuguJPNTranslator

parser = argparse.ArgumentParser(description='run fugu translate server')
parser.add_argument('config_file', help='config json file')

args = parser.parse_args()
CONFIG = json.load(open(args.config_file))

log_file = os.path.join(CONFIG["log_dir"], "server.log")
logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO, filename=log_file)
logger = logging.getLogger()
logger.setLevel(0)

bottle.BaseRequest.MEMFILE_MAX = CONFIG["memfile_max"]

FGMT = FuguJPNTranslator(CONFIG["webserver_marian_ports"], retry_max=3, retry_wait=30.0, timeout=300)


def read_template(filename):
    with open(filename, encoding="utf-8") as in_file:
        ret = in_file.read()
    return ret


def get_file_id(post_fix=""):
    return "{}_{}_{}".format(uuid.uuid4(), time.time(), re.sub("\W","_", post_fix))


def ret_auth_check(config, auth_idx):
    auth_user = config["auth_info"][auth_idx]["username"]
    auth_password = config["auth_info"][auth_idx]["password"]

    def auth_check(username, password):
        if len(auth_user) and len(auth_password):
            return username == auth_user and password == auth_password
        else:
            return True

    return auth_check


@bottle.route("/")
def html_index():
    tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["index"])
    return bottle.template(read_template(tmpl_file), webserver_max_len_en=CONFIG["webserver_max_len_en"]
                           , webserver_max_len_en_simple=CONFIG["webserver_max_len_en_simple"])


auth_check_static = ret_auth_check(CONFIG, "static")
@bottle.route("/static/<filepath:path>", name="static_file")
def static(filepath):
    static_dir = CONFIG["static_dir"]
    path = os.path.abspath(os.path.join(static_dir, filepath))
    if not re.search("^%s" % static_dir, path):
        return "internal err"
    return bottle.static_file(filepath, root=static_dir)


auth_check_pdf = ret_auth_check(CONFIG, "pdf")
@bottle.route("/show_pdf/<filepath:path>", name="static_file")
@bottle.auth_basic(auth_check_pdf)
def static_pdf(filepath):
    static_dir = CONFIG["pdf_dir"]
    path = os.path.abspath(os.path.join(static_dir, filepath))
    if not re.search("^%s" % static_dir, path):
        return "internal err"
    return bottle.static_file(filepath, root=static_dir)


@bottle.route("/pdf/<page:int>/<pdf_name>")
@bottle.auth_basic(auth_check_pdf)
def show_pdf(page, pdf_name):
    try:
        if not re.match(r"^[a-zA-Z0-9\-\_\.]+$", pdf_name):
            return "pdf_name err"
        pickle_path = os.path.join(CONFIG["pickle_dir"], pdf_name + ".pickle")
        pickle_data = pickle.load(open(pickle_path, "rb"))
        show_data = []
        add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}

        for translated in pickle_data[page]:
            best_is_norm = 1
            add_item["scores"].append(translated["ja_best_score"])
            add_item["en"] += translated["en"]
            add_item["ja_best"] += translated["ja_best"]
            add_item["ja_norm"] += translated["ja_norm"]
            if translated["best_is_norm"] == 0:
                best_is_norm = 0
            if len(add_item["ja_best"]) < 10:
                continue
            show_data.append({
                "best_is_norm": best_is_norm,
                "en": break_word(add_item["en"]),
                "ja_norm": break_word(add_item["ja_norm"]),
                "ja_best": break_word(add_item["ja_best"]),
                "ja_best_score": sum(add_item["scores"]) / len(add_item["scores"])
            })
            add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}
        page_list = [idx for idx, v in enumerate(pickle_data)]
        tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["translate_pdf"])
        return bottle.template(read_template(tmpl_file), show_data=show_data, pdf_name=pdf_name,
                               page=page, page_list=page_list)
    except:
        logger.error(pprint.pformat(sys.exc_info()))
        err_text = "Error"
        tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["message"])
        return bottle.template(read_template(tmpl_file), message=err_text, back_url="/")


# for upload
@bottle.route('/pdf_upload', method='POST')
@bottle.auth_basic(auth_check_pdf)
def do_upload():
    db_file = CONFIG["db_file"]
    upload = bottle.request.files.get('upload', '')
    if not upload.filename.lower().endswith('.pdf'):
        return 'File extension not allowed!'

    logger.info("original_file_name = {}".format(upload.filename))
    grp = re.search("(\.[^\.]+$)", upload.filename)
    extension = grp.group(1)

    tmp_filename = get_file_id(post_fix="{}_{}".format(
        bottle.request.environ.get('HTTP_X_FORWARDED_FOR'), bottle.request.environ.get('REMOTE_ADDR')
    )) + "tmp"
    save_path_tmp = os.path.join(CONFIG["pdf_dir"], tmp_filename)
    try:
        chunk_size = 64 * 1024
        total_read = chunk_size
        out = open(save_path_tmp, "wb")
        buf = upload.file.read(chunk_size)
        while buf:
            out.write(buf)
            buf = upload.file.read(chunk_size)
            total_read += chunk_size
            if total_read > CONFIG["upload_limit"]:
                out.close()
                return "FILE too large"
        out.close()
    except:
        logger.warn(pprint.pformat(sys.exc_info()))

    try:
        save_file_name = get_file_id(post_fix="{}_{}".format(
            bottle.request.environ.get('HTTP_X_FORWARDED_FOR'), bottle.request.environ.get('REMOTE_ADDR'))) + extension
        save_path = os.path.join(CONFIG["pdf_dir"], save_file_name)
        os.rename(save_path_tmp, save_path)

        with sqlite3.connect(db_file, timeout=120) as db_con:
            db_con = sqlite3.connect(db_file)
            ret = db_con.execute('insert into status(pdf_name, pdf_path_name, status, date_str) values (?, ?, ?, ?);',
                                 (upload.filename, save_file_name, 'uploaded', datetime.today())).fetchone()
            db_con.commit()

            status_list = []
            for row in db_con.execute(
                    'SELECT pdf_name, pdf_path_name, status, date_str from status order by date_str desc;'):
                status_list.append((row[0], row[1], row[2], row[3]))

        tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["message"])
        return bottle.template(read_template(tmpl_file), message="upload:" + save_file_name, back_url="/pdf_upload")

    except:
        logger.warn(pprint.pformat(sys.exc_info()))
        return "Internal Error"


@bottle.route('/pdf_upload', method='GET')
@bottle.auth_basic(auth_check_pdf)
def list_upload():
    db_file = CONFIG["db_file"]
    status_list = []
    with sqlite3.connect(db_file, timeout=120) as db_con:
        for row in db_con.execute(
                'SELECT pdf_name, pdf_path_name, status, date_str from status order by date_str desc;'):
            status_list.append((break_word(row[0]), row[1], row[2], row[3]))
    tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["translate_pdf_upload"])
    return bottle.template(read_template(tmpl_file), message="", status_list=status_list)


@bottle.route("/en_ja/", method="POST")
def en_ja():
    en_text = bottle.request.forms.getunicode("en_text")
    if len(en_text) > CONFIG["webserver_max_len_en_simple"]:
        err_text = "文字数が長すぎます。{}文字以内としてください。".format(CONFIG["webserver_max_len_en_simple"])
        tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["message"])
        return bottle.template(read_template(tmpl_file), message=err_text, back_url="/")

    FGMT.use_sentence_tokenize = False
    translated = FGMT.translate_text(en_text)
    logger.info(FGMT.get_and_clear_logs())
    tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["translate"])
    return bottle.template(read_template(tmpl_file), show_data=translated[0])


@bottle.route("/en_ja_detail/", method="POST")
def en_ja_detail():
    start = time.time()
    en_text = bottle.request.forms.getunicode("en_text")

    if len(en_text) > CONFIG["webserver_max_len_en"]:
        err_text = "文字数が長すぎます。{}文字以内としてください。".format(CONFIG["webserver_max_len_en"])
        tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["message"])
        return bottle.template(read_template(tmpl_file), message=err_text, back_url="/")
    else:
        FGMT.use_sentence_tokenize = True
        translated, candidate, candidate_parse = FGMT.translate_text(en_text, ret_internal_data=True)
        logger.info(FGMT.get_and_clear_logs())

    tmpl_file = os.path.join(CONFIG["template_dir"], CONFIG["html_templates"]["translate_detail"])
    return bottle.template(read_template(tmpl_file), translated=translated, candidate=candidate,
                           candidate_parse=candidate_parse)


def main():
    bottle.run(host=CONFIG["webserver_host"], port=CONFIG["webserver_port"])


if __name__ == '__main__':
    main()
