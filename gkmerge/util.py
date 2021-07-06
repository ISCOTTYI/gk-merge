import logging
import random
from randomdict import RandomDict
from gkmerge.bank import Bank

logger = logging.getLogger(__name__)


def sample_unique_pair(rd: RandomDict):
    if len(rd) < 2:
        raise ValueError("Need RandomDict of length 2 or more!")
    b, d = rd.random_key(), rd.random_key()
    while b == d:
        d = rd.random_key()
    return b, d


def sample_except(rd: RandomDict, exclude):
    if len(rd) < 2:
        raise ValueError("Need RandomDict of length 2 or more!")
    b = rd.random_key()
    while b == exclude:
        b = rd.random_key()
    return b


def _pairs(l):
    """Yield n number of striped chunks from l."""
    if len(l) % 2 != 0:
        raise ValueError("Odd list cannot be split into pairs")
    n = int(len(l) / 2)
    return [l[i::n] for i in range(0, n)]


def random_pairs(rd: RandomDict):
    """
    Returns list of tuples of rd's keys
    """
    if len(rd) % 2 != 0 or len(rd) == 0:
        raise ValueError("Need RandomDict of even length!")
    rd_lst = list(rd)
    random.shuffle(rd_lst)
    return _pairs(rd_lst)


def insert_dict(insert_to, insert_from):
    """
    Inserts the keys of insert_from into insert_to and adds values if dicts share specific key
    """
    for k, v in insert_from.items():
        if k in insert_to:
            insert_to[k] += v
        else:
            insert_to[k] = v
