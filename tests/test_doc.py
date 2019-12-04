"""
Testing for textpipe doc.py
"""
import pytest
import random
import spacy
import numpy as np
from fakeredis import FakeRedis
from unittest import mock

from textpipe.doc import Doc, TextpipeMissingModelException, RedisIDFWeightingMismatchException
from textpipe.wrappers import RedisKeyedVectors

TEXT_1 = """<p><b>Text mining</b>, also referred to as <i><b>text data mining</b></i>, roughly
equivalent to <b>text analytics</b>, is the process of deriving high-quality <a href="/wiki/Information"
title="Information">information</a> from <a href="/wiki/Plain_text" title="Plain text">text</a>.
High-quality information is typically derived through the devising of patterns and trends through means
such as <a href="/wiki/Pattern_recognition" title="Pattern recognition">statistical pattern learning</a>.
Text mining usually involves the process of structuring the input text (usually parsing, along with the
addition of some derived linguistic features and the removal of others, and subsequent insertion into a
<a href="/wiki/Database" title="Database">database</a>), deriving patterns within the
<a href="/wiki/Structured_data" class="mw-redirect" title="Structured data">structured data</a>, and
finally evaluation and interpretation of the output. Google is a company named Google.
"""

TEXT_2 = """<p><b>Textmining</b>, ook wel <i>textdatamining</i>, verwijst naar het proces om met
allerhande<a href="/wiki/Informatietechnologie" title="Informatietechnologie">ICT</a>-technieken
waardevolle informatie te halen uit grote hoeveelheden tekstmateriaal. Met deze technieken wordt
gepoogd patronen en tendensen te ontwaren. Concreet gaat men teksten softwarematig structureren
en ontleden, transformeren, vervolgens inbrengen in databanken, en ten slotte evalueren en
interpreteren. Philips is een bedrijf genaamd Philips.</p>
"""

TEXT_3 = ''

TEXT_4 = """this is a paragraph
this is a paragraph
"""

TEXT_5 = """Mark Zuckerberg is sinds de oprichting van Facebook de directeur van het bedrijf."""

TEXT_6 = """
မြန်မာဘာသာစကားသည် တိဘက်-ဗမာနွယ် ဘာသာစကားများ အုပ်စုတွင် ပါဝင်သည်။
တိဘက်-ဗမာနွယ် ဘာသာစကားများ အုပ်စုသည် တရုတ်-တိဗက်နွယ် ဘာသာစကားများ
မိသားစု ထဲတွင် ပါသည်။ မြန်မာဘာသာသည် တက်ကျသံရှိသော
၊နိမ့်မြင့်အမှတ်အသားရှိ ဖြစ်သော၊ ဧကဝဏ္ဏစကားလုံး အလွန်များသော ဘာသာစကား
ဖြစ်သည်။ ကတ္တား-ကံ-တြိယာ စကားလုံးအစီအစဉ်ဖြင့် ရေးသော သရုပ်ခွဲဘာသာစကား
လည်းဖြစ်သည်။ မြန်မာအက္ခရာများသည် ဗြာဟ္မီအက္ခရာ သို့မဟုတ် ဗြာဟ္မီအက္ခရာမှ
ဆက်ခံထားသောမွန်အက္ခရာတို့မှ ဆင်းသက်လာသည်။
"""

TEXT_7 = u"""\nHi <<First Name>>\nthis is filler text \xa325 more filler.\nadditilnal 
filler.\nyet more\xa0still more\xa0filler.\n\xa0\nmore\nfiller.\x03\n\t\t\t\t\t\t    
almost there \n\\n\nthe end\n"""

ents_model = spacy.blank('nl')
custom_spacy_nlps = {'nl': {'ents': ents_model}}

DOC_1 = Doc(TEXT_1)
DOC_2 = Doc(TEXT_2)
DOC_3 = Doc(TEXT_3)
DOC_4 = Doc(TEXT_4)
DOC_5 = Doc(TEXT_5, spacy_nlps=custom_spacy_nlps)
DOC_6 = Doc(TEXT_6)
DOC_7 = Doc(TEXT_7)


def test_load_custom_model():
    """
    The custom spacy language modules should be correctly loaded into the doc.
    """
    model_mapping = {'nl': 'ents'}
    lang = DOC_5.language if DOC_5.is_reliable_language else DOC_5.hint_language
    assert lang == 'nl'
    assert sorted(DOC_5.find_ents()) == sorted([('Mark Zuckerberg', 'PER'), ('Facebook', 'PER')])
    assert DOC_5.find_ents(model_mapping[lang]) == []


def test_nwords_nsents():
    assert DOC_1.nwords == 112
    assert DOC_2.nwords == 65
    assert DOC_3.nwords == 0
    assert DOC_1.nsents == 4
    assert DOC_2.nsents == 4
    assert DOC_3.nsents == 0


def test_entities():
    assert sorted(DOC_1.ents) == sorted([('Google', 'ORG')])
    assert sorted(DOC_2.ents) == sorted([('Philips', 'ORG')])
    assert DOC_3.ents == []


def test_complexity():
    assert DOC_1.complexity == 30.464548969072155
    assert DOC_2.complexity == 17.652500000000003
    assert DOC_3.complexity == 100


def test_clean():
    assert len(TEXT_1) >= len(DOC_1.clean)
    assert len(TEXT_2) >= len(DOC_2.clean)
    assert len(TEXT_3) >= len(DOC_3.clean)


def test_clean_newlines():
    assert ' '.join(TEXT_4.split()) == DOC_4.clean


def test_language():
    assert DOC_1.language == 'en'
    assert DOC_2.language == 'nl'
    assert DOC_3.language == 'un'


def test_extract_keyterms():
    non_ranker = 'bulthaup'
    rankers = ['textrank', 'sgrank', 'singlerank']
    with pytest.raises(ValueError, message=f'algorithm "{non_ranker}" not '
                                           f'available; use one of {rankers}'):
        DOC_1.extract_keyterms(ranker=non_ranker)
    assert len(DOC_1.extract_keyterms()) == 10
    # limits number of keyterms
    assert len(DOC_1.extract_keyterms(n_terms=2)) == 2
    # works with empty documents
    assert DOC_3.extract_keyterms() == []
    # works with other rankers
    assert isinstance(DOC_2.extract_keyterms(ranker=random.choice(rankers)), list)


def test_missing_language_model():
    with pytest.raises(TextpipeMissingModelException):
        DOC_6.nwords


def test_minhash_similarity():
    assert DOC_1.similarity(DOC_2) == 0.0625


def test_non_utf_chars():
    assert DOC_7.language == 'en'


def test_gensim_word2vec():
    expected_doc_2 = [0.0076740906, -0.051765148, -0.008963874, -0.16817021, -0.12640671,
                      -0.28199115, -0.1418166, -0.08547635, -0.1489038, 0.049820565]
    actual_doc_2 = Doc(TEXT_2).generate_gensim_document_embedding(
        model_uri='tests/models/gensim_test_nl.kv')
    if not np.allclose(actual_doc_2, expected_doc_2):
        raise AssertionError

    expected_doc_5 = [0.04336167, -0.12551728, 0.121972464, -0.023885678, -0.0892916, 0.011041589,
                      -0.022286428, 0.06333805, 0.07664292, 0.086685486]
    actual_doc_5 = Doc(TEXT_5).generate_gensim_document_embedding(
        model_uri='tests/models/gensim_test_nl.kv',
        idf_weighting='naive')
    if not np.allclose(actual_doc_5, expected_doc_5):
        raise AssertionError

    expected_doc_5 = [0.021136083, -0.035798773, 0.032576967, 0.0048801005, -0.028301004,
                      -0.0059328717, -0.010782357, 0.025319293, 0.018113682, 0.028851084]
    actual_doc_5 = Doc(TEXT_5).generate_gensim_document_embedding(
        model_uri='tests/models/gensim_test_nl.kv',
        idf_weighting='log')
    if not np.allclose(actual_doc_5, expected_doc_5):
        raise AssertionError


@mock.patch('textpipe.wrappers.Redis', FakeRedis)
def test_gensim_word2vec_with_redis():
    # Load word2vec model into fake Redis
    kv = RedisKeyedVectors('redis://host:1234/0', 'nl')
    kv.load_keyed_vectors_into_redis('tests/models/gensim_test_nl.kv')

    expected_doc_2 = [0.0076740906, -0.051765148, -0.008963874, -0.16817021, -0.12640671,
                      -0.28199115, -0.1418166, -0.08547635, -0.1489038, 0.049820565]
    actual_doc_2 = Doc(TEXT_2, gensim_vectors={'nl': kv}). \
        generate_gensim_document_embedding(model_uri='redis://host:1234/0')
    if not np.allclose(actual_doc_2, expected_doc_2):
        raise AssertionError(actual_doc_2)

    expected_doc_5 = [0.04336167, -0.12551728, 0.121972464, -0.023885678, -0.0892916, 0.011041589,
                      -0.022286428, 0.06333805, 0.07664292, 0.086685486]
    actual_doc_5 = Doc(TEXT_5).generate_gensim_document_embedding(model_uri='redis://host:1234/0',
                                                                  idf_weighting='naive')
    if not np.allclose(actual_doc_5, expected_doc_5):
        raise AssertionError

    with pytest.raises(RedisIDFWeightingMismatchException) as e:
        Doc(TEXT_5).generate_gensim_document_embedding(model_uri='redis://host:1234/0',
                                                       idf_weighting='log')
    assert str(e.value) == 'The specified document embedding idf weighting "log" does not match ' \
                           'weighting in RedisKeyedVector "naive"'

    kv = RedisKeyedVectors('redis://host:1234/0', 'nl')
    kv.load_keyed_vectors_into_redis('tests/models/gensim_test_nl.kv', idf_weighting='log')
    expected_doc_5 = [0.02113608, -0.035798773, 0.032576967, 0.0048801005, -0.028301004,
                      -0.005932871, -0.010782358, 0.025319293, 0.018113682, 0.028851084]
    actual_doc_5 = Doc(TEXT_5, gensim_vectors={'nl': kv}).\
        generate_gensim_document_embedding(model_uri='redis://host:1234/0', idf_weighting='log')

    if not np.allclose(actual_doc_5, expected_doc_5):
        raise AssertionError
    kv._redis.flushall()


@mock.patch('textpipe.wrappers.Redis', FakeRedis)
def test_gensim_word2vec_with_redis_no_model():
    with pytest.raises(TextpipeMissingModelException) as e:
        Doc(TEXT_2).generate_gensim_document_embedding(model_uri='redis://host:1234/0')
    assert str(e.value) == 'Redis does not contain a model for language nl. The model' \
                           ' needs to be loaded before use (see load_keyed_vectors_into_redis).'


def test_textrank_summary():
    assert len(DOC_1.generate_textrank_summary(ratio=0.5)) == 2


def test_lead():
    assert len(DOC_1.extract_lead(nsents=1)) == 1
    assert len(DOC_1.extract_lead(nsents=2)) == 2
    assert len(DOC_1.extract_lead(nsents=50)) == DOC_1.nsents
