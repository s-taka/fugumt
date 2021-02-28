import re
import time
import datetime
import os
import sys
import pprint

from websocket import create_connection
from websocket import WebSocketTimeoutException
from multiprocessing import Pool

import numpy as np

import nltk
import MeCab
from allennlp.predictors.predictor import Predictor
import allennlp_models.structured_prediction
import tensorflow_hub as hub
import tensorflow_text

from fugumt.misc import cos_sim
from fugumt.misc import clean_txt
from fugumt.misc import to_one_line

import timeout_decorator
from fugumt.misc import translate_marian


def translate_marian_multi(args):
    en_text, port, timeout, retry_max, retry_wait, batch_size = args
    return translate_marian(en_text, port, timeout, retry_max, retry_wait, batch_size)

def get_err_translated():
    return [{"best_is_norm": 0,
            "en": "err",
            "ja_best": "翻訳エラー",
            "ja_best_score": 0.0,
            "ja_norm": "翻訳エラー",
            "ja_norm_score": 0.0,
            "ja_parse": "翻訳エラー",
            "ja_parse_score": 0.0
            }]


class FuguJPNTranslator:
    def __init__(self, marian_ports, use_sentence_tokenize=True, use_constituency_parsing=True,
                 timeout=600, retry_max=3, retry_wait=10, batch_size=5, can_translate_func=None):
        # info = "struct": {table name: [col_name: operation]}
        self.marian_ports = marian_ports
        self.global_pool = Pool(len(marian_ports))
        self.detected_marian_err = False
        self.use_sentence_tokenize = use_sentence_tokenize
        self.timeout = timeout
        self.retry_max = retry_max
        self.retry_wait = retry_wait
        self.batch_size = batch_size

        def default_can_translate(en_txt):
            if re.search("[a-zA-Z]", en_txt):
                return True
            else:
                return False
        if can_translate_func:
            self.can_translate = can_translate_func
        else:
            self.can_translate = default_can_translate

        if use_sentence_tokenize:
            from nltk.tokenize import sent_tokenize
            nltk.download('punkt')

            def sent_tokenize_en(txt):
                ary = sent_tokenize(clean_txt(re.sub("\r?\n\r?\n", ".\n", txt)))
                return [v for v in filter(lambda x: len(x) > 0, [clean_txt(s) for s in ary])]

            self.sent_tokenize_en = sent_tokenize_en

        self.use_constituency_parsing = use_constituency_parsing
        if use_constituency_parsing:
            self.constituency_parser = Predictor.from_path(
                "https://storage.googleapis.com/allennlp-public-models/elmo-constituency-parser-2020.02.10.tar.gz")

        self.logs = []

        self.embed = hub.load("https://tfhub.dev/google/universal-sentence-encoder-multilingual/3")
        self.wakati = MeCab.Tagger("-Owakati")

    def logger_write(self, message):
        self.logs.append("{}\t{}".format(datetime.datetime.now().strftime("%Y/%m/%d %H:%M:%S"), message))

    def get_and_clear_logs(self):
        ret_logs = "\n".join(self.logs)
        self.logs = []
        return ret_logs

    def comp_en_ja_tokens(self, txt_en, txt_ja):
        en_len = len(nltk.word_tokenize(txt_en))
        ja_len = len(self.wakati.parse(txt_ja).split())
        return (en_len + 1.0) / (ja_len + 1.0)

    def partition_txt(self, txt):
        if len(txt.split()) < 15:
            return [txt]

        def _proc_part(_root_part, _ret, _buf_txt):
            for part in _root_part:
                part_word = part["word"]
                part_type = part["nodeType"]
                self.logger_write("{}:[{}]".format(part_word, part_type))
                if (part_type == 'S' and len(part_word.split()) < 20) or part_type == 'PRN':
                    if len(_buf_txt.split()) > 3:
                        _ret.append(_buf_txt)
                        _ret.append(part_word)
                    else:
                        _ret.append(_buf_txt + part_word)
                    _buf_txt = ""
                elif part_type == 'CC' and len(_buf_txt.split()) > 10:
                    _ret.append(_buf_txt)
                    _buf_txt = part_word + " "
                elif (part_type == ',' or part_type == '.') and len(_buf_txt.split()) > 10:
                    _ret.append(_buf_txt + part_word)
                    _buf_txt = ""
                elif (part_type == ',' or part_type == '.' or part_type == "''" or
                      part_type == "'" or part_type == '"') and len(_buf_txt.split()) == 0:
                    if len(_ret) > 0:
                        _ret[-1] += part_word
                        _buf_txt = ""
                    else:
                        _buf_txt = part_word
                elif len(part_word.split()) < 10:
                    _buf_txt += part_word + " "
                else:
                    _buf_txt = _proc_part(part['children'], _ret, _buf_txt)
            return _buf_txt

        parsed_txt = self.constituency_parser.predict(sentence=txt)
        root_part = parsed_txt["hierplane_tree"]["root"]["children"]
        ret = []
        buf_txt = ""
        last_buf = _proc_part(root_part, ret, buf_txt)
        if len(ret) == 0:
            ret.append(last_buf)
            last_buf = ""
        partitioned_list = []
        buf = ""
        for r in ret:
            if len(r) > 3:
                partitioned_list.append(re.sub(" ,", ",", buf + r).replace("  "," "))
                buf = ""
            else:
                buf += r + " "
        if len(last_buf.split()) < 3:
            partitioned_list[-1] += last_buf
        else:
            partitioned_list.append(last_buf)
        return partitioned_list

    def translate_texts(self, texts):
        ret = []
        for text in texts:
            ret.append(self.translate_text(text))
        return ret

    def translate_text(self, text, ret_internal_data=False):
        if len(text) == 0:
            return []
        ret = []
        en_text = re.sub("\r?\n\r?\n", "\n\n", text)
        text_list = en_text.split("\n\n")
        en_sentences = []
        for tmp_txt in text_list:
            tmp_txt = re.sub("\s*\-\r?\n\s*", "", tmp_txt)
            tmp_txt = re.sub("\r?\n", " ", tmp_txt)
            if self.use_sentence_tokenize:
                en_sentences += self.sent_tokenize_en(tmp_txt)
            else:
                en_sentences += [tmp_txt]
        translate_sentence_length = len(en_sentences)
        idx_partitioned_idx = {}
        for idx in range(translate_sentence_length):
            ens = en_sentences[idx]
            if self.use_constituency_parsing:
                partitioned = self.partition_txt(ens)
            else:
                partitioned = []
            if len(partitioned) > 1:
                idx_partitioned_idx[idx] = []
                partitioned_idx = len(en_sentences)
                for pts in partitioned:
                    en_sentences.append(pts)
                    idx_partitioned_idx[idx].append(partitioned_idx)
                    partitioned_idx += 1
        # default: can_translate a-zA-Zが含まれていない場合はmarianへ投入除外
        for_translate_tmp = []
        en_idx2translated_idx = {}
        en_sentece_with_part_length = len(en_sentences)
        for i, s in enumerate(en_sentences):
            if self.can_translate(s):
                en_idx2translated_idx[i] = len(for_translate_tmp)
                for_translate_tmp.append(s)
        for_translate = "\n".join([re.sub("\r?\n$", "", s) for s in for_translate_tmp])
        try:
            # translate
            ja_text_list = self.global_pool.map(translate_marian_multi, [
                (for_translate, p, self.timeout, self.retry_max, self.retry_wait, self.batch_size)
                for p in self.marian_ports])
            for ja_text in ja_text_list:
                if len(ja_text[1]):
                    self.logger_write("marian process err:{}".format(ja_text[1]))
                    self.detected_marian_err = True
            ret_candidates = []
            ret_candidates_with_parse = []
            for ja_text in ja_text_list:
                # a-zA-Zが含まれていない場合はmarianへ投入除外
                ja_sentences_tmp = ja_text[0].split("\n")
                ja_sentences = []
                for idx in range(en_sentece_with_part_length):
                    if idx in en_idx2translated_idx:
                        ja_sentences.append(ja_sentences_tmp[en_idx2translated_idx[idx]])
                    else:
                        ja_sentences.append(en_sentences[idx])

                en_vecs = self.embed(en_sentences)
                ja_vecs = self.embed(ja_sentences)
                out_tuples = []
                out_tuples_with_parse = []
                for idx in range(translate_sentence_length):
                    ens = en_sentences[idx]
                    jns = ja_sentences[idx]
                    word_rate = self.comp_en_ja_tokens(ens, jns)
                    ej_score = cos_sim(en_vecs[idx], ja_vecs[idx]) * min(word_rate / 0.85, 0.85 / word_rate)
                    out_tuples.append((ej_score, ens, jns))

                    if idx in idx_partitioned_idx:
                        jns = ""
                        for pidx in idx_partitioned_idx[idx]:
                            jns += ja_sentences[pidx] + " "
                        ja_concat_vec = self.embed([jns])[0]
                        word_rate = self.comp_en_ja_tokens(ens, jns)
                        ej_score = cos_sim(en_vecs[idx], ja_concat_vec) * min(word_rate / 0.85, 0.85 / word_rate)
                    out_tuples_with_parse.append((ej_score, ens, jns))
                ret_candidates.append(out_tuples)
                ret_candidates_with_parse.append(out_tuples_with_parse)

            for idx in range(translate_sentence_length):
                best_translate = max([r[idx] for r in ret_candidates])
                best_translate_with_parse = max([r[idx] for r in ret_candidates_with_parse])
                if best_translate_with_parse[0] * 0.9 > best_translate[0]:
                    ret.append({
                        "best_is_norm": 0,
                        "en": best_translate_with_parse[1],
                        "ja_best": best_translate_with_parse[2],
                        "ja_best_score": best_translate_with_parse[0],
                        "ja_norm": best_translate[2],
                        "ja_norm_score": best_translate[0],
                        "ja_parse": best_translate_with_parse[2],
                        "ja_parse_score": best_translate_with_parse[0]
                    })
                else:
                    ret.append({
                        "best_is_norm": 1,
                        "en": best_translate_with_parse[1],
                        "ja_best": best_translate[2],
                        "ja_best_score": best_translate[0],
                        "ja_norm": best_translate[2],
                        "ja_norm_score": best_translate[0],
                        "ja_parse": best_translate_with_parse[2],
                        "ja_parse_score": best_translate_with_parse[0]
                    })
        except Exception as e:
            self.logger_write("Unexpected error in translate_texts:{}".format(pprint.pformat(sys.exc_info())))
            raise e
        if ret_internal_data:
            return ret, ret_candidates, ret_candidates_with_parse
        return ret

