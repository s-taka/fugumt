FROM ubuntu:18.04

LABEL maintainer "staka@vole.jp"

RUN apt-get update && apt-get -y upgrade
RUN apt-get install -y tzdata
ENV TZ=Asia/Tokyo 

RUN apt-get install -y language-pack-ja-base language-pack-ja
RUN locale-gen en_US.UTF-8  
ENV LANG en_US.UTF-8  
ENV LANGUAGE en_US:en  
ENV LC_ALL en_US.UTF-8

RUN apt-get install -y git curl cmake build-essential python3-pip libpq-dev python-dev python3-setuptools libatlas-* libopenblas-*

RUN apt-get install -y git cmake build-essential libboost-all-dev libprotobuf10 protobuf-compiler libprotobuf-dev openssl libssl-dev libgoogle-perftools-dev libprotobuf10 protobuf-compiler libprotobuf-dev wget
RUN wget -qO- 'https://apt.repos.intel.com/intel-gpg-keys/GPG-PUB-KEY-INTEL-SW-PRODUCTS-2019.PUB' | apt-key add -
RUN sh -c 'echo deb https://apt.repos.intel.com/mkl all main > /etc/apt/sources.list.d/intel-mkl.list'
RUN apt-get update
RUN apt-get install -y intel-mkl-64bit-2020.0-088
RUN mkdir /app
WORKDIR /app
RUN git clone https://github.com/marian-nmt/marian
WORKDIR /app/marian/
RUN mkdir -p build
WORKDIR /app/marian/build
RUN cmake ../ -DCOMPILE_CPU=on -DCOMPILE_CUDA=off -DUSE_SENTENCEPIECE=on -DCOMPILE_SERVER=on
RUN make -j4

RUN pip3 install --upgrade pip

RUN pip3 install bottle websocket_client h5py

RUN apt-get install -y mecab libmecab-dev mecab-ipadic-utf8 
RUN pip3 install mecab-python3 unidic-lite

RUN pip3 install --upgrade numpy==1.16.0 scipy==1.4.1 setuptools>=41.0.0
RUN pip3 install tf-sentencepiece "tensorflow_hub>=0.6.0" "tensorflow==2.3.0" tensorflow_text>=2.0.0rc0 nltk bert-for-tf2 allennlp allennlp-models psutil timeout-decorator
RUN pip3 install pdfminer
RUN pip3 install spacy
RUN python3 -m spacy download en_core_web_sm
RUN chmod -R 755 /app/marian/build

RUN pip3 install feedparser beautifulsoup4
RUN pip3 install gunicorn