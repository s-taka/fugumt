Fugu-Machine Translator
====

[ぷるーふおぶこんせぷと](https://staka.jp/wordpress/?p=413)
で公開した機械翻訳エンジンを利用する翻訳環境です。
フォームに入力された文字列の翻訳、PDFの翻訳が可能です。

あくまで検証用の環境・ソフトウェアであり、公開サーバ上での実行を想定したものではありません。
（上記BLOGで公開されているWEB環境で用いているソフトウェアではありません。）

Usage
----

### 翻訳サーバの実行
Dockerがセットアップされている場合、下記のように実行できます。
1. git clone後、model/ 以下に「[FuguMT model](https://fugumt.com/FuguMT_ver.202011.1.zip) 」で配布されているモデルをダウンロード、展開
   - ``git clone http://github.com/s-taka/fugumt``
   - ``wget https://fugumt.com/FuguMT_ver.202011.1.zip``
   - ``shasum FuguMT_ver.202011.1.zip``
     - ハッシュ値が 0cf8a1fc540b4c7b4388b75b71858c0eb32e392a であることを確認
   - ``unzip FuguMT_ver.202011.1.zip``
   - 解凍した場所から移動 ``mv model/* fugumt/model``
2. Docker環境を構築
   - ``cd fugumt/docker``
   - ``docker build -t fugu_mt .``
3. コンテナを実行
   - ``docker run -v /path_to/fugumt/:/app/fugu_mt -p 127.0.0.1:8888:8080 -it --user `id -u`:`id -g` --rm fugu_mt
python3 /app/fugu_mt/run.py /app/fugu_mt/config.json``
   - 「/path_to」は環境に合わせて変更してください。git cloneを行った先のディレクトリを指定する必要があります。
   - Load completeと表示されたら実行ができています。

実行後、http://localhost:8888/
にアクセスすることで翻訳エンジンを利用可能です。

http://localhost:8888/pdf_upload/
からPDFの翻訳を行うことができます。
パスワードはconfig.jsonの"auth_info"から設定可能です。
デフォルトではpdf/pdfとなっています。

本ソフトウェアは信頼できるネットワーク上での実行を前提に利用してください。


### pdfの翻訳
翻訳サーバの実行の2.まで構築が終わっていれば、環境変数を設定し、コマンドラインからPDFを翻訳することもできます。
1. Dockerコンテナ起動
   * docker run -v /path_to/fugumt/:/app/fugu_mt -it --user `id -u`:`id -g` --rm fugu_mt bash

2. 環境変数を設定
```shell
export TFHUB_CACHE_DIR=/app/fugu_mt/cache/
export NLTK_DATA=/app/fugu_mt/cache/
export ALLENNLP_CACHE_ROOT=/app/fugu_mt/cache/
```
3. コマンド実行
   * ``python3 /app/fugu_mt/pdf_server.py --pdf Dockerコンテナ上のPDFパス 
     --out Dockerコンテナ上のpickle保存場所 
     --out_html Dockerコンテナ上のHTML保存場所
     --mk_process 1 
     /app/fugu_mt/config.json``


### marian-decoderの実行

より簡易にモデルを試す場合は以下の手順でテストが可能です。
Docker build、モデルのダウンロードは「翻訳サーバの実行」と同じです。

* ``docker run -v /path_to/fugumt/:/app/fugu_mt -it --user `id -u`:`id -g` --rm fugu_mt
bash``
   * 「/path_to」は環境に合わせて変更してください。git cloneを行った先のディレクトリを指定する必要があります。
* ``cd /app/fugu_mt``
* ``echo "Fugu MT model" | /app/marian/build/marian-decoder -c model/model.npz.decoder.yml``

下記のように_uncasedを指定すると、大文字・小文字を無視した翻訳を行います。
* ``echo "Fugu MT model" | /app/marian/build/marian-decoder -c model/model_uncased.npz.decoder.yml``

### fugumtライブラリの実行

ライブラリを通した翻訳は下記のように実行することができます。
Docker build、モデルのダウンロードは「翻訳サーバの実行」と同じです。

1. 環境変数を設定
```shell
export TFHUB_CACHE_DIR=/app/fugu_mt/cache/
export NLTK_DATA=/app/fugu_mt/cache/
export ALLENNLP_CACHE_ROOT=/app/fugu_mt/cache/
```
2. pythonコードを実行（python3を実行後に入力）
```python
# ライブラリをimport
from fugumt.tojpn import FuguJPNTranslator
from fugumt.misc import make_marian_process
from fugumt.misc import close_marian_process

# marian processを作成
marian_processes = make_marian_process("/app/marian/build/marian-server",
                                       [["-p","8001","-c","model/model.npz.decoder.yml", "--log", "log/marian8001.log"]],
                                       [8001])

# 翻訳
fgmt = FuguJPNTranslator([8001])
translated = fgmt.translate_text("This is a Fugu machine translator.")
print(translated)

# marian processをクローズ
close_marian_process(marian_processes)

```
3. translate_textが返す値は下記の構造となっています。複数の文が入力された場合はlistにappendされます。
訳抜け防止モードの説明は「 [
機械翻訳と訳抜けとConstituency parsing](https://staka.jp/wordpress/?p=357) 」をご参照下さい。
```python
[{'best_is_norm': 1, # 通常翻訳のスコアが良い場合は1、訳抜け防止モードが良い場合は0
  'en': 'This is a Fugu machine translator.', # 入力された英文
  'ja_best': 'ふぐ機械翻訳機。', # スコアが一番良かった日本語訳
  'ja_best_score': 0.2991045981645584, # 上記スコア
  'ja_norm': 'ふぐ機械翻訳機。', # 通常翻訳で一番良かった日本語訳
  'ja_norm_score': 0.2991045981645584, # 上記スコア
  'ja_parse': 'ふぐ機械翻訳機。', # 訳抜け防止モードで一番良かった日本語訳
  'ja_parse_score': 0.2991045981645584 # 上記スコア
  }]
```


謝辞・ライセンス
----

本ソフトウェアは下記のライブラリ・ソフトウェアを利用しています。
またDockerfileに記載の通り、ubuntuで使用可能なパッケージを多数使用しています。
OSSとして素晴らしいソフトウェアを公開された方々に感謝いたします。

* Marian-NMT (MIT-License): https://github.com/marian-nmt/marian
* SentencePiece(Apache-2.0 License): https://github.com/google/sentencepiece
* NLTK (Apache License Version 2.0): https://www.nltk.org/
* MeCab (BSDライセンス): https://taku910.github.io/mecab/
* mecab-python3 (Like MeCab itself, mecab-python3 is copyrighted free software by Taku Kudo taku@chasen.org and Nippon Telegraph and Telephone Corporation, and is distributed under a 3-clause BSD license ): https://github.com/SamuraiT/mecab-python3
* unidic-lite(BSD license): https://github.com/polm/unidic-lite
* bottle (MIT-License): https://bottlepy.org/docs/dev/
* gunicorn (MIT License): https://github.com/benoitc/gunicorn
* tensorflow (Apache 2.0): https://github.com/tensorflow/tensorflow
* Universal Sentence Encoder (Apache 2.0): https://tfhub.dev/google/universal-sentence-encoder/3
* allennlp (Apache 2.0):https://github.com/allenai/allennlp , [AllenNLP: A Deep Semantic Natural Language Processing Platform](https://www.semanticscholar.org/paper/AllenNLP%3A-A-Deep-Semantic-Natural-Language-Platform-Gardner-Grus/a5502187140cdd98d76ae711973dbcdaf1fef46d)
* spacy (MIT License): https://spacy.io/
* pdfminer (MIT-License): https://github.com/euske/pdfminer
* websocket-client (BSD-3-Clause License): https://github.com/websocket-client/websocket-client
* psutil(BSD-3-Clause License): https://github.com/giampaolo/psutil
* timeout-decorator (MIT License): https://github.com/pnpnpn/timeout-decorator 
* bootstrap(MIT-License) : https://getbootstrap.com/
* jquery(MIT-License): https://jquery.com/
* DataTables(MIT-License): https://datatables.net/

本ソフトウェアは研究用を目的に公開しています。
作者（Satoshi Takahashi）は本ソフトウェアの動作を保証せず、本ソフトウェアを使用して発生したあらゆる結果について一切の責任を負いません。
本ソフトウェア（Code）はMIT-Licenseです。

モデル作成では上記ソフトウェアに加え、下記のデータセット・ソフトウェアを使用しています。
オープンなライセンスでソフトウェア・データセットを公開された方々に感謝いたします。
* Beautiful Soap (MIT License): https://www.crummy.com/software/BeautifulSoup/
* feedparser (BSD License): https://github.com/kurtmckee/feedparser
* LaBSE (Apache 2.0): https://tfhub.dev/google/LaBSE/
  * Fangxiaoyu Feng, Yinfei Yang, Daniel Cer, Narveen Ari, Wei Wang. Language-agnostic BERT Sentence Embedding. July 2020
* Japanese-English Subtitle Corpus (CC BY-SA 4.0): https://nlp.stanford.edu/projects/jesc/
  * Pryzant, R. and Chung, Y. and Jurafsky, D. and Britz, D.,
    JESC: Japanese-English Subtitle Corpus,
    Language Resources and Evaluation Conference (LREC), 2018
* 京都フリー翻訳タスク (KFTT) (CC BY-SA 3.0): http://www.phontron.com/kftt/index-ja.html
  * Graham Neubig, "The Kyoto Free Translation Task," http://www.phontron.com/kftt, 2011.
* Tanaka Corpus (CC BY 2.0 FR):http://www.edrdg.org/wiki/index.php/Tanaka_Corpus
  * > Professor Tanaka originally placed the Corpus in the Public Domain, and that status was maintained for the versions used by WWWJDIC. In late 2009 the Tatoeba Project decided to move it to a Creative Commons CC-BY licence (that project is in France, where the concept of public domain is not part of the legal framework.) It can be freely downloaded and used provided the source is attributed. 
* JSNLI (CC BY-SA 4.0):http://nlp.ist.i.kyoto-u.ac.jp/index.php?%E6%97%A5%E6%9C%AC%E8%AA%9ESNLI%28JSNLI%29%E3%83%87%E3%83%BC%E3%82%BF%E3%82%BB%E3%83%83%E3%83%88
  * 吉越 卓見, 河原 大輔, 黒橋 禎夫: 機械翻訳を用いた自然言語推論データセットの多言語化, 第244回自然言語処理研究会, (2020.7.3).
* WikiMatrix (Creative Commons Attribution-ShareAlike license):https://github.com/facebookresearch/LASER/tree/master/tasks/WikiMatrix
  * Holger Schwenk, Vishrav Chaudhary, Shuo Sun, Hongyu Gong and Paco Guzman, WikiMatrix: Mining 135M Parallel Sentences in 1620 Language Pairs from Wikipedia, arXiv, July 11 2019.
* Tatoeba (CC BY 2.0 FR): https://tatoeba.org/jpn
  * > https://tatoeba.org TatoebaのデータはCC-BY 2.0 FRで提供されています。
* CCAligned (No claims of intellectual property are made on the work of preparation of the corpus. ): http://www.statmt.org/cc-aligned/
  * El-Kishky, Ahmed and Chaudhary, Vishrav and Guzm{\'a}n, Francisco and Koehn, Philipp,
    CCAligned: A Massive Collection of Cross-lingual Web-Document Pairs,
    Proceedings of the 2020 Conference on Empirical Methods in Natural Language Processing (EMNLP 2020), 2020


ニューラル機械翻訳モデル「[FuguMT model](http://plant-check.jp:8080/static/FuguMT_ver.202011.1.zip) 」は
上記に独自収集データを加えMarian-NMT + SentencePieceで作成しています。
モデル構築に使用したデータ量は約660万対訳ペア、V100 GPU 1つを用いて約30時間学習しています。

「FuguMT model ver.202011.1」のライセンスは[CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.ja)
です。

本モデルは研究用を目的に公開しています。
作者（Satoshi Takahashi）は本モデルの動作を保証せず、本モデルを使用して発生したあらゆる結果について一切の責任を負いません。

※ FuguMT model ver.202011.1ではTatoeba、CCAlignedは使用しておらず、ver.202101.1以降のモデルで使用予定です。

※ 出典を書く際はBlogのURL記載またはリンクをお願いします。
 https://staka.jp/wordpress/
