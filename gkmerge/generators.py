import logging
import random
import functools
import numpy as np
from itertools import permutations
from gkmerge.network import Network
from gkmerge.bank import Bank

logger = logging.getLogger(__name__)

__all__ = [
    "complete",
    "circular"
]


def seed_homogenous_balance_sheets(banks, alpha, kappa):
    """
    For a given list of banks, initialize the balance sheets. Assets are
    distributed evenly over incoming links.

    :param alpha: fraction of interbank assets of total assets, 0 < alpha < 1
    :type alpha: float
    :param kappa: fraction of capital of total assets, 0 < kappa < 1
    :type kappa: float
    """
    if not 0 <= alpha <= 1 or not 0 <= alpha <= 1:
        raise ValueError("alpha and kappa must be between 0 and 1")

    assets_tot = 100
    homogenous_capital = assets_tot * kappa

    for b in banks:
        if len(b.predecessors) > 0:
            assets_ib = assets_tot * alpha
            assets_ib_per_pre = assets_ib / len(b.predecessors)
            b.balance_sheet["assets_ib"] = assets_ib
            b.balance_sheet["assets_e"] = assets_tot - assets_ib
        else:
            assets_ib_per_pre = 0
            b.balance_sheet["assets_ib"] = 0
            b.balance_sheet["assets_e"] = assets_tot
        for pre in b.predecessors:
            b.predecessors[pre] = assets_ib_per_pre
            pre.successors[b] = assets_ib_per_pre
    for b in banks:
        liabilities_ib = sum(b.successors.values())
        b.balance_sheet["liabilities_ib"] = liabilities_ib
        b.balance_sheet["liabilities_e"] = assets_tot - liabilities_ib - homogenous_capital
    return homogenous_capital


def complete(n, alpha, kappa):
    banks = {}
    for _ in range(n):
        new_b = Bank()
        banks[new_b] = new_b
    for u, v in permutations(banks, 2):
        u.successors[v] = 0
        v.predecessors[u] = 0
    homo_cap = seed_homogenous_balance_sheets(banks, alpha, kappa)
    return Network(banks=banks)


def circular(n, alpha, kappa):
    banks = {}
    for _ in range(n):
        new_b = Bank()
        banks[new_b] = new_b
    banks_lst = list(banks)
    for i in range(n):
        u = banks_lst[i]
        v = banks_lst[(i + 1) % n]
        u.successors[v] = 0
        v.predecessors[u] = 0
    homo_cap = seed_homogenous_balance_sheets(banks, alpha, kappa)
    return Network(banks=banks)


def erdos_renyi(n, p, alpha, kappa):
    banks = {}
    for _ in range(n):
        new_b = Bank()
        banks[new_b] = new_b
    for u, v in permutations(banks, 2):
        if random.random() < p:
            u.successors[v] = 0
            v.predecessors[u] = 0
    homo_cap = seed_homogenous_balance_sheets(banks, alpha, kappa)
    return Network(banks=banks)


def from_unique_id_link_list(n, links, alpha, kappa):
    """
    Create network from list of links with unique bank ids and no gaps in ids.
    Example: [[1, 2], [3, 1]]
    """
    banks = {}
    banks_by_id = {}
    for _ in range(n):
        new_b = Bank()
        banks[new_b] = new_b
        banks_by_id[new_b.id_] = new_b
    for link in links:
        u = banks_by_id[link[0]]
        v = banks_by_id[link[1]]
        u.successors[v] = 0
        v.predecessors[u] = 0
    homo_cap = seed_homogenous_balance_sheets(banks, alpha, kappa)
    return Network(banks=banks)


def from_adjacency_matrix(ad_mat):
    raise NotImplementedError()
