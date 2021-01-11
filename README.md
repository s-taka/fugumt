Fugu-Machine Translator
====

[ぷるーふおぶこんせぷと](https://staka.jp/wordpress/)
で公開（予定）の機械翻訳エンジンを利用する翻訳環境です。
フォームに入力された文字列の翻訳、PDFの翻訳が可能です。

あくまで検証用の環境・ソフトウェアであり、公開サーバ上での実行を想定したものではありません。
（上記BLOGで公開されているWEB環境で用いているソフトウェアではありません。）

Usage
----
Dockerがセットアップされている場合、下記のように実行できます。
1. git clone後、model/ 以下に「」で配布されているモデルをダウンロード、展開
   - ``git clone http://github.com/s-taka/fugumt``
   - ``wget http://plant-check.jp:8080/static/FuguMT_ver.202011.1.zip``
   - ``shasum FuguMT_ver.202011.1.zip``
     - ハッシュ値が e4437af43bc4068dafbbbe815fc792b21daf8a66 であることを確認
   - ``unzip FuguMT_ver.202011.1.zip``
   - 解凍した場所から移動 ``mv model/* fugumt/model``
2. Docker環境を構築
   - ``cd fugumt/docker``
   - ``docker build -t fugu_mt .``
3. コンテナを実行
   - ``docker run -v /path_to/fugu_mt/:/app/fugu_mt -p 127.0.0.1:8888:8080 -it --user `id -u`:`id -g` --rm fugu_mt
python3 /app/fugu_mt/run.py /app/fugu_mt/config.json``
   - Load completeと表示されたら実行ができています。

実行後、http://localhost:8888/
にアクセスすることで翻訳エンジンを利用可能です。

http://localhost:8888/pdf_upload/
からPDFの翻訳を行うことができます。
パスワードはconfig.jsonの"auth_info"から設定可能です。
デフォルトではpdf/pdfとなっています。

本ソフトウェアは信頼できるネットワーク上での実行を前提に利用してください。

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
* tensorflow (Apache 2.0): https://github.com/tensorflow/tensorflow
* Universal Sentence Encoder (Apache 2.0): https://tfhub.dev/google/universal-sentence-encoder/3
* allennlp (Apache 2.0): [AllenNLP: A Deep Semantic Natural Language Processing Platform](https://www.semanticscholar.org/paper/AllenNLP%3A-A-Deep-Semantic-Natural-Language-Platform-Gardner-Grus/a5502187140cdd98d76ae711973dbcdaf1fef46d)
* spacy (MIT License): https://spacy.io/
* pdfminer (MIT-License): https://github.com/euske/pdfminer
* websocket-client (BSD-3-Clause License): https://github.com/websocket-client/websocket-client
* psutil(BSD-3-Clause License): https://github.com/giampaolo/psutil
* timeout-decorator (MIT License): https://github.com/pnpnpn/timeout-decorator 
* bootstrap(MIT-License) : https://getbootstrap.com/
* jquery(MIT-License): https://jquery.com/
* DataTables(MIT-License): https://datatables.net/

本ソフトウェアは研究用を目的に公開しています。
作者は本ソフトウェアの動作を保証せず、本ソフトウェアを使用して発生したあらゆる結果について一切の責任を負いません。
本ソフトウェア（Code）はMIT-Licenseです。

モデル作成では上記ソフトウェアに加え、下記のデータセット・ソフトウェアを使用しています。
オープンなライセンスでソフトウェア・データセットを公開された方々に感謝いたします。
* Beautiful Soap (MIT License): https://www.crummy.com/software/BeautifulSoup/
* LaBSE (Apache 2.0): https://tfhub.dev/google/LaBSE/1
* Japanese-English Subtitle Corpus (CC BY-SA 4.0): https://nlp.stanford.edu/projects/jesc/
* 京都フリー翻訳タスク (KFTT) (CC BY-SA 3.0): http://www.phontron.com/kftt/index-ja.html
* Tanaka Corpus (CC BY 2.0 FR):http://www.edrdg.org/wiki/index.php/Tanaka_Corpus
* JSNLI (CC BY-SA 4.0):http://nlp.ist.i.kyoto-u.ac.jp/index.php?%E6%97%A5%E6%9C%AC%E8%AA%9ESNLI%28JSNLI%29%E3%83%87%E3%83%BC%E3%82%BF%E3%82%BB%E3%83%83%E3%83%88
* WikiMatrix (Creative Commons Attribution-ShareAlike license):https://github.com/facebookresearch/LASER/tree/master/tasks/WikiMatrix
* Tatoeba (CC BY 2.0 FR): https://tatoeba.org/jpn
* CCAligned (No claims of intellectual property are made on the work of preparation of the corpus. ): http://www.statmt.org/cc-aligned/

ニューラル機械翻訳モデル「FuguMT model（URL）」は上記に独自収集データを加え作成しています。
「FuguMT model ver.202011.1」のライセンスは[CC-BY SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.ja)
です。

本モデルは研究用を目的に公開しています。
作者は本モデルの動作を保証せず、本モデルを使用して発生したあらゆる結果について一切の責任を負いません。

※ FuguMT model ver.202011.1ではTatoeba、CCAlignedは使用しておらず、ver.202101.1以降のモデルで使用予定です。
