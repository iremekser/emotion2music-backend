from typing import List
from jpype import JClass, JString, getDefaultJVMPath, shutdownJVM, startJVM, java
import re
import json
import numpy as np
from gensim.models import Word2Vec
from os import path
import random

stops = [
    'acaba', 'ama', 'aslında', 'az', 'bazı', 'belki', 'biri', 'birkaç',
    'birşey', 'biz', 'bu', 'çok', 'çünkü', 'da', 'daha', 'de', 'defa', 'diye',
    'eğer', 'en', 'gibi', 'hem', 'hep', 'hepsi', 'her', 'hiç', 'için', 'ile',
    'ise', 'kez', 'ki', 'kim', 'mı', 'mu', 'mü', 'nasıl', 'ne', 'neden',
    'nerde', 'nerede', 'nereye', 'niçin', 'niye', 'o', 'sanki', 'şey', 'siz',
    'şu', 'tüm', 've', 'veya', 'ya', 'yani'
]
printable = set(
    '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ!"#$%&\'()*+,-./:;<=>?@[\\]^_`{|}~ \t\n\r\x0b\x0c'
)
printable.update(list("öçşüğı"))

def clear(text, morphology):
# girilen cumledeki stopWords'ler kaldirilir
# olusturulan morphology e gore kokler alinir
# cumle icindeki isaretler kaldirilir
    text = text.replace('İ', 'i').replace('I', 'ı').lower().split()
    text = ' '.join([i for i in text if i not in stops])
    analysis: java.util.ArrayList = (
        morphology.analyzeAndDisambiguate(text).bestAnalysis())
    pos: List[str] = []
    for i, analysis in enumerate(analysis, start=1):
        s = str(analysis.getLemmas()[0]).strip()
        if s.lower() != 'unk':
            pos.append(s)
        else:
            pos.append(str(analysis.getDictionaryItem().pronunciation))

    text = ' '.join(pos)

    clean = re.sub(r"""
               [,.;@#?!&$-<>*':\\"`]+  
               """,
                   "",
                   text,
                   flags=re.VERBOSE)

    x = ''.join(filter(lambda x: x in printable, clean)).strip().split(' ')
    newX = []
    for i in x:
        newX.append(i.strip())
    return ' '.join(newX).replace('  ', ' ').replace('unk', '')


def read_txt(file, morphology):
# veri setlerini temizleyip okuma islemi
    with open(file) as f:
        return [clear(i.replace('\n', ''), morphology) for i in f.readlines()]


def avg_sentence_vector(words, model, num_features):
# cumlelerin vektorleri olusturulurken kullanilir
    featureVec = np.zeros((num_features, ), dtype="float32")
    nwords = 0
    for word in words:
        if word in model.wv.index2word:
            nwords = nwords + 1
            featureVec = np.add(featureVec, model.wv[word]**2)
    if nwords > 0:
        featureVec = np.divide(featureVec, nwords)

    return featureVec.reshape(1, -1)


def similarity(sentence, main_data, model):
# kullanicidan alinan sentence ile veri seti karsilastirilir
# uyumluluk hesaplanir
    vec1 = avg_sentence_vector(sentence.split(), model=model, num_features=100)
    results = []
    for i in main_data:
        vec2 = avg_sentence_vector(i.split(), model=model, num_features=100)
        sim = cosine(vec1, vec2)
        results.append(sim)
    results.sort(reverse=True)
    return sum(results[:5]) / 5


def cosine(u, v):
# iki vektorun uyumlulugunu hesaplarken kullanılan fonksiyon
    u = u[0]
    v = v[0]
    dot = sum([a * b for a, b in zip(list(u), list(v))])
    norm_a = sum([a * a for a in u])**0.5
    norm_b = sum([b * b for b in v])**0.5
    if norm_a * norm_b:
        return dot / (norm_a * norm_b)
    else:
        return 0


def generate_model(main_data, name, morphology):
# word2vec algoritmasina gore model olusturma
    if path.isfile(name + '.bin'):
        model = Word2Vec.load(name + '.bin')
        model.vocab = model.wv.vocab
        model.index2word = model.wv.index2word
        return model

    big_title_string = ' '.join(main_data)
    big_title_string = clear(big_title_string, morphology)
    tokens = big_title_string.split()
    words = [word.lower() for word in tokens if word.isalpha()]
    words = [word for word in words if not word in stops]
    sentences = [i.split() for i in main_data]
    model = Word2Vec(sentences, min_count=1, size=100)
    words = list(model.wv.vocab)
    model.save(name + '.bin')
    model = Word2Vec.load(name + '.bin')
    model.vocab = model.wv.vocab
    model.index2word = model.wv.index2word
    return model


def read_song_json(filename):
# sarkilarin oldugu json dosyalarini okuma
    with open(filename) as f:
        return json.loads(f.read())


def test(morphology):
# programi test etmek icin elimizdeki verilerin %25 i alinir
# kalan kisimla karsilastirilir
    neg = read_txt('data/negatif.txt', morphology)
    pos = read_txt('data/pozitif.txt', morphology)
    neg_test, neg_train = neg[:int(len(neg) / 4)], neg[int(len(neg) / 4):]
    pos_test, pos_train = pos[:int(len(pos) / 4)], pos[int(len(pos) / 4):]

    neg_model = generate_model(neg_train, 'test_neg', morphology)
    pos_model = generate_model(pos_train, 'test_pos', morphology)

    neg_results = []
    pos_results = []
    print("Negative test")
    for index, s in enumerate(neg_test):
        r_neg = similarity(s, neg_train, neg_model)
        r_pos = similarity(s, pos_train, pos_model)
        if r_neg > r_pos:
            x = 0
        elif r_neg < r_pos:
            x = 1
        else:
            x = -1

        print(index, 'Pozitif' if x else 'Negatif', s,r_neg, r_pos)
        neg_results.append(x)

    print("Positive test")
    for index, s in enumerate(pos_test):
        r_neg = similarity(s, neg_train, neg_model)
        r_pos = similarity(s, pos_train, pos_model)
        if r_neg > r_pos:
            x = 0
        elif r_neg < r_pos:
            x = 1
        else:
            x = -1

        print('Pozitif' if x else 'Negatif', s, r_neg, r_pos)
        pos_results.append(x)

    return neg_results, pos_results


def predict(s, morphology):
# kullanicinin girdigi sentence'a gore gerceklestirilen islemler
    s = clear(s, morphology)
    negative = read_txt('data/negatif.txt', morphology)
    positive = read_txt('data/pozitif.txt', morphology)

    neg_model = generate_model(negative, 'negative', morphology)
    pos_model = generate_model(positive, 'positive', morphology)

    pos_skor = similarity(s, positive, pos_model)
    neg_skor = similarity(s, negative, neg_model)
    print("neg:", neg_skor)
    print("pos:", pos_skor)
    if pos_skor < neg_skor:
        result = 0
    elif pos_skor > neg_skor:
        result = 1
    else:
        result = -1
    return {'negative': neg_skor, 'positive': pos_skor, 'result': result}


def suggest_song(result):
# duygu durumuna gore cikan sonuca gore sarki onerisi
    if result['result'] == 1:
        tracks = read_song_json('data/happy_songs.json')
    elif result['result'] == 0:
        tracks = read_song_json('data/sad_songs.json')
    else:
        return None
    return random.choice(tracks)