# -*- coding: utf-8 -*-


import pickle
import argparse
import json
import logging
from datetime import datetime

import time
import sys
import os
import sqlite3
import pprint
import base64
import re
import html

import subprocess
import psutil

from subprocess import PIPE
from subprocess import TimeoutExpired

from io import StringIO
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser

from fugumt.tojpn import FuguJPNTranslator
from fugumt.tojpn import get_err_translated

from fugumt.misc import make_marian_process
from fugumt.misc import close_marian_process
from fugumt.misc import ckeck_restart_marian_process

def escape_break_word(txt):
    return re.sub('([a-zA-Z0-9\/\.\-\:\%\-\~\\\*\"\'\&\$\#\(\)\?\_\,,\@]{20,}?)', "\\1 ", html.escape(txt))


def pre_proc_text(txt):
    return txt


def pdf_translate(pdf_path, fgmt, make_marian_conf=None, logger=None):
    page_split_tag = '\n\n<<PAGE_SPLIT_TAG>>\n\n'
    output_string = StringIO()
    with open(pdf_path, 'rb') as in_file:
        parser = PDFParser(in_file)
        doc = PDFDocument(parser)
        rsrcmgr = PDFResourceManager()
        device = TextConverter(rsrcmgr, output_string, laparams=LAParams(boxes_flow=0.3, line_margin=1.0))
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        for idx, page in enumerate(PDFPage.create_pages(doc)):
            interpreter.process_page(page)
            output_string.write(page_split_tag)
    pdf_text = output_string.getvalue()
    pdf_pages = pdf_text.split(page_split_tag)
    marian_processes = []
    if make_marian_conf:
        marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                               make_marian_conf["marian_args_pdf_translator"],
                                               make_marian_conf["pdf_ports"])
    ret = []
    for pdf_idx, pdf_page in enumerate(pdf_pages[:-1]):
        retry_max = 3
        translated = None
        for i in range(retry_max):
            if logger:
                logger.info("translate page={}".format(pdf_idx))
            to_translate = pre_proc_text(pdf_page)
            translated = fgmt.translate_text(to_translate)
            if not fgmt.detected_marian_err:
                ret.append(translated)
                break
            else:
                translated = None
                close_marian_process(marian_processes)
                marian_processes = make_marian_process(make_marian_conf["marian_command"],
                                                       make_marian_conf["marian_args_pdf_translator"],
                                                       make_marian_conf["pdf_ports"])

                fgmt.detected_marian_err = False
                if logger:
                    logger.info(fgmt.get_and_clear_logs())
                    logger.warning("recovery marian processes {}/{}".format(i, retry_max-1))
        if translated is None:
            ret.append(get_err_translated())
        marian_processes = ckeck_restart_marian_process(marian_processes, make_marian_conf["max_marian_memory"],
                                                        make_marian_conf["marian_command"],
                                                        make_marian_conf["marian_args_pdf_translator"],
                                                        make_marian_conf["pdf_ports"],
                                                        logger=logger)
        if logger:
            logger.info(fgmt.get_and_clear_logs())

    if make_marian_conf:
        close_marian_process(marian_processes)

    return ret


def do_db(db_file, pdf_dir, pickle_dir, fgmt, make_marian_conf=None, logger=None, template=""):
    pdf_name = ""
    status = ""
    try:
        with sqlite3.connect(db_file, timeout=120) as db_con:
            ret = db_con.execute('SELECT pdf_path_name, status FROM status WHERE status=? order by date_str;',
                                 ('uploaded',)).fetchone()
            if ret:
                pdf_name = ret[0]
                status = ret[1]
    except:
        return pprint.pformat(sys.exc_info())

    if len(pdf_name) > 0:
        try:
            ret_str = "process [{}]\n".format(pdf_name)
            with sqlite3.connect(db_file) as db_con:
                ret = db_con.execute('UPDATE status set status=?, date_str=? WHERE pdf_path_name=?;',
                                     ('translate to jpn', datetime.today(), pdf_name)).fetchone()
                db_con.commit()
            pdf_path = os.path.join(pdf_dir, pdf_name)
            ret = pdf_translate(pdf_path, fgmt, make_marian_conf=make_marian_conf, logger=logger)

            with open(os.path.join(pickle_dir, pdf_name + ".pickle"), "wb") as f:
                pickle.dump(ret, f)

            with sqlite3.connect(db_file, timeout=120) as db_con:
                ret = db_con.execute('UPDATE status set status=?, date_str=? WHERE pdf_path_name=?;',
                                     ('complete', datetime.today(), pdf_name)).fetchone()
                db_con.commit()
            ret_str += fgmt.get_and_clear_logs()

            if len(template):
                make_static_html(pdf_path, os.path.join(pickle_dir, pdf_name + ".pickle"),
                                 pdf_path + ".html", template=template)
            return ret_str
        except:
            with sqlite3.connect(db_file, timeout=120) as db_con:
                ret = db_con.execute('UPDATE status set status=? WHERE pdf_path_name=?;',
                                     ('error', pdf_name)).fetchone()
                db_con.commit()
            return pprint.pformat(sys.exc_info())
    return "Nothing to do."


def make_static_html(pdf_path, pickle_path, html_path, template="template/pdf_server_static.tmpl", add_data=""):
    with open(template, encoding="utf-8") as in_file:
        tmpl = in_file.read()

    with open(pdf_path, "rb") as in_pdf:
        pdf_base64 = base64.b64encode(in_pdf.read()).decode("utf-8")

    table_header_tmpl = "<div id='translated_{}'><table border='1'><tr><th>英語</th><th>日本語</th><th>スコア</th></tr>\n"
    table_footer_tmpl = "</table></div>\n"
    tr_tmpl = "<tr> <td>{}</td> <td>{}</td> <td>{:.2f}</td></tr>\n"
    tr_tmpl_parse = "<tr> <td>{}</td> <td>{} <br /><small>訳抜け防止モード: {}</small></td> <td>{:.2f}</td></tr>\n"

    pickle_data = pickle.load(open(pickle_path, "rb"))
    translated_tables = ""
    for page_num, translated_page in enumerate(pickle_data):
        translated_tables += table_header_tmpl.format(page_num+1)
        add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}
        for translated in translated_page:
            best_is_norm = 1
            add_item["scores"].append(translated["ja_best_score"])
            add_item["en"] += translated["en"]
            add_item["ja_best"] += translated["ja_best"]
            add_item["ja_norm"] += translated["ja_norm"]
            if translated["best_is_norm"] == 0:
                best_is_norm = 0
            if len(add_item["ja_best"]) < 10:
                continue
            show_score = sum(add_item["scores"]) / len(add_item["scores"])
            if best_is_norm == 1:
                translated_tables += tr_tmpl.format(escape_break_word(add_item["en"]),
                                                    escape_break_word(add_item["ja_best"]), show_score)
            else:
                translated_tables += tr_tmpl_parse.format(escape_break_word(add_item["en"]),
                                                          escape_break_word(add_item["ja_norm"]),
                                                          escape_break_word(add_item["ja_best"]),
                                                          show_score)
            add_item = {"en": "", "ja_best": "", "ja_norm": "", "scores": []}
        if len(add_item["en"]):
            show_score = sum(add_item["scores"]) / len(add_item["scores"])
            translated_tables += tr_tmpl.format(escape_break_word(add_item["en"]),
                                                escape_break_word(add_item["ja_best"]), show_score)
        translated_tables += table_footer_tmpl

    page_list_tmpl = "<button id='nav_{}' onclick='renderPage({})'>{}</button>\n"
    page_list = "&nbsp;".join([page_list_tmpl.format(idx+1, idx+1, idx+1) for idx in range(len(pickle_data))])

    with open(html_path, "w") as out:
        write_data = tmpl.replace("{{translated_tables}}", translated_tables)
        write_data = write_data.replace("{{navigation}}", page_list)
        write_data = write_data.replace("{{base64_pdf}}", pdf_base64)
        write_data = write_data.replace("{{add_data}}", add_data)
        out.write(write_data)

    return

def main():
    parser = argparse.ArgumentParser(description='run fugu machine translator for pdf')
    parser.add_argument('config_file', help='config json file')
    parser.add_argument('--pdf', help='PDF file')
    parser.add_argument('--out', help='out pickle file')
    parser.add_argument('--mk_process', help='make marian process')
    parser.add_argument('--out_html', help='out html file')

    args = parser.parse_args()
    config = json.load(open(args.config_file))

    root_dir = config["app_root"]
    pickle_dir = config["pickle_dir"]
    pdf_file = ""
    if args.pdf:
        pdf_file = args.pdf
        out_pickle_file = args.out

    out_html_file = ""
    if args.out_html:
        out_html_file = args.out_html

    make_marian_conf = None
    if args.mk_process:
        make_marian_conf = config
    log_file = os.path.join(config["log_dir"], "pdf_server.log")

    logging.basicConfig(format='%(asctime)s : %(levelname)s : %(message)s', level=logging.INFO, filename=log_file)
    logger = logging.getLogger()
    logger.setLevel(0)

    fgmt = FuguJPNTranslator(config["pdf_ports"], retry_max=0, batch_size=3)

    if pdf_file:
        if not os.path.exists(out_pickle_file):
            logger.info("translate [{}]".format(pdf_file))
            ret = pdf_translate(pdf_file, fgmt, make_marian_conf=make_marian_conf, logger=logger)
            with open(out_pickle_file, "wb") as f:
                pickle.dump(ret, f)
            logger.info(fgmt.get_and_clear_logs())
        else:
            logger.info("file {} exist. omit translating".format(out_pickle_file))

    if out_html_file:
        logger.info("make html  [{}]".format(pdf_file))
        make_static_html(pdf_file, out_pickle_file, out_html_file,
                         template=os.path.join(config["template_dir"], config["static_pdfhtml_template"]))

    if not pdf_file:
        while True:
            logger.info("translate check db")
            ret = do_db(config["db_file"], config["pdf_dir"], config["pickle_dir"], fgmt,
                        make_marian_conf=make_marian_conf, logger=logger,
                        template=os.path.join(config["template_dir"], config["static_pdfhtml_template"]))
            if ret:
                logger.info("do_db[{}]".format(ret))
            logger.info("sleep {} sec".format(config["sleep_sec"]))
            time.sleep(config["sleep_sec"])


if __name__ == '__main__':
    main()





