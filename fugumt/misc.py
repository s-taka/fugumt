# -*- coding: utf-8 -*-
import re
import time
import sys
import pprint

from subprocess import PIPE
from subprocess import TimeoutExpired

import numpy as np

import psutil

from websocket import create_connection
from websocket import WebSocketTimeoutException

import timeout_decorator


@timeout_decorator.timeout(240)
def _translate_marian(ws, batch):
    ws.send(batch.rstrip())
    return ws.recv()


def translate_marian(en_text, port, timeout=300, retry_max=3, retry_wait=30.0, batch_size=10):
    ja_text = ""
    err_text = ""
    if len(en_text) < 1 or len(en_text.strip()) < 1:
        return "", ""
    for i in range(retry_max + 1):
        ja_text = ""
        try:
            count = 0
            batch = ""
            ws = create_connection("ws://localhost:{}/translate".format(port), timeout=timeout)
            for line in en_text.split("\n"):
                count += 1
                batch += line + "\n"
                if count == batch_size:
                    result = _translate_marian(ws, batch)
                    ja_text += result
                    count = 0
                    batch = ""
            if count:
                result = _translate_marian(ws, batch)
                ja_text += result
            ws.close()
            return ja_text, err_text
        except:
            retry_max += -1
            err_text += "[WARNING] Unexpected error in translate_marian retry:{}\n".format(pprint.pformat(sys.exc_info()))
            err_text += "[WARNING] ERROR TEXT:".join(["{}\n".format(s) for s in batch.split("\n")])
            try:
                ws.close()
            except:
                err_text += "cannot close ws\n"
        if retry_max <= 0:
            ja_text = "(翻訳err)\n" * len(en_text.split("\n"))
            err_text += "[ERROR] Unexpected error in translate_marian:{}\n".format(pprint.pformat(sys.exc_info()))
            err_text += "[ERROR] Unexpected error in translate_marian_input len:{} sentences_num:{}\n".format(
                len(en_text), len(en_text.split("\n")))
            err_text += "[ERROR] Unexpected error in translate_marian_input sentence:{}\n".format(pprint.pformat(en_text))
            return ja_text, err_text
        else:
            time.sleep(retry_wait)
    ja_text = "[ERROR] Error"
    err_text = "[ERROR] unexpected_err"
    return ja_text, err_text


def wait_marian_loaded(marian_ports):
    for port in marian_ports:
        ret = translate_marian("This is a status check for the marian process.", port)
    return 0


def make_marian_process(marian_command, marian_args, marian_ports):
    marian_servers = []
    for marian_arg in marian_args:
        marian_servers.append(psutil.Popen([marian_command] + marian_arg))
        # stderr=PIPE, stdout=PIPE, encoding='utf-8', errors="ignore"))
        time.sleep(5.0)
    try:
        wait_marian_loaded(marian_ports)
        return marian_servers
    except:
        close_marian_process(marian_servers)
        raise TimeoutExpired


@timeout_decorator.timeout(30)
def close_marian_process(marian_processes):
    for marian_proc in marian_processes:
        marian_proc.kill()
        outs, errs = marian_proc.communicate()
        time.sleep(1.0)
    return 0


@timeout_decorator.timeout(30)
def ckeck_restart_marian_process(marian_processes, max_memory, marian_command, marian_args, marian_ports, logger=None):
    for marian_proc in marian_processes:
        memory_info = marian_proc.memory_info()
        if logger:
            logger.info("mem usage={}".format(memory_info.rss))
        else:
            print("mem usage={}".format(memory_info.rss))
        if memory_info.rss > max_memory:
            if logger:
                logger.info("mem usage={} reload marian servers ".format(memory_info.rss))
            else:
                print("mem usage={} reload marian servers ".format(memory_info.rss))
            close_marian_process(marian_processes)
            return make_marian_process(marian_command, marian_args, marian_ports)
    return marian_processes


def cos_sim(lhs, rhs):
    return np.dot(lhs, rhs) / (np.linalg.norm(lhs) * np.linalg.norm(rhs))


def clean_txt(txt):
    ret = re.sub(r"^\r?\n?", "", txt.replace(u'\xa0', u' '))
    ret = re.sub(r"(\r\n)+", "\n", ret)
    ret = re.sub(r"\n+", "\n", ret)
    ret = re.sub(r"\r+", "\n", ret)
    return ret


def to_one_line(txt):
    return re.sub("^(\s|\W)+", "", txt.replace("\r", "").replace("\n", "").replace("\t", ""))


def break_word(txt):
    return re.sub('([a-zA-Z0-9\/\.\-\:\%\-\~\\\*\"\'\&\$\#\(\)\?\_\,\@]{20,}?)', "\\1 ", txt)
