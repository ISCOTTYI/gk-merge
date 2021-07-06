import logging
import random
import math
# import functools
# import numpy as np
from itertools import permutations
from randomdict import RandomDict
from gkmerge.network import Network
from gkmerge.bank import Bank

logger = logging.getLogger(__name__)

__all__ = [
    "unlinked",
    "complete",
    "circular",
    "erdos_renyi",
    "fast_erdos_renyi",
    "from_unique_id_link_list"
]


def seed_homogenous_balance_sheets(network, alpha, kappa):
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
    homog_cap = assets_tot * kappa
    net = network
    for b in net.banks:
        in_deg = net.in_deg_of(b)
        if in_deg > 0:
            assets_ib = assets_tot * alpha
            assets_ib_per_pre = assets_ib / in_deg
            b.balance_sheet["assets_ib"] = assets_ib
            b.balance_sheet["assets_e"] = assets_tot - assets_ib
        else:
            assets_ib_per_pre = 0
            b.balance_sheet["assets_ib"] = 0
            b.balance_sheet["assets_e"] = assets_tot
        for pre in net.pres_of(b):
            net.add_or_update_link(pre, b, weight=assets_ib_per_pre, update_balance_sheets=False)
    for b in net.banks:
        liabilities_ib = sum([suc_weight[1] for suc_weight in net.sucs_of(b, weight=True)])
        b.balance_sheet["liabilities_ib"] = liabilities_ib
        b.balance_sheet["liabilities_e"] = assets_tot - liabilities_ib - homog_cap
    return homog_cap


def unlinked(n):
    """
    Create network with given number n of banks
    """
    net = Network()
    for _ in range(n):
        b = Bank()
        net.add_bank(b)
    return net


def complete(n, alpha, kappa):
    net = unlinked(n)
    for u, v in permutations(net.banks, 2):
        # balance_sheets all 0 and weights all 0 too -> no need to update balance_sheets
        net.add_or_update_link(u, v, update_balance_sheets=False)
    homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
    return net


def circular(n, alpha, kappa):
    net = unlinked(n)
    banks_lst = list(net.banks)
    for i in range(n):
        u = banks_lst[i]
        v = banks_lst[(i + 1) % n]
        net.add_or_update_link(u, v, update_balance_sheets=False)
    homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
    return net


def erdos_renyi(n, p, alpha, kappa):
    net = unlinked(n)
    for u, v in permutations(net.banks, 2):
        if random.random() < p:
            net.add_or_update_link(u, v, update_balance_sheets=False)
    homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
    return net


def fast_erdos_renyi(n, p, alpha, kappa):
    """
    V. Batagelj and Ulrik Brandes, "Efficient generation of large random networks",
    Phys Rev E 71, (2005)
    """
    net = Network()
    banks_numbered = {}
    for i in range(n):
        b = Bank()
        net.add_bank(b)
        banks_numbered[i] = b
    if p >= 1:
        raise ValueError("p must be smaller than 1! Generate complete graph instead.")
    if p <= 0:
        homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
        return net
    u, v, logp = 0, -1, math.log(1.0 - p)
    while u < n:
        logr = math.log(1.0 - random.random())
        v = v + 1 + int(logr / logp)
        if u == v:
            v += 1
        while u < n <= v:
            v = v - n
            u = u + 1
            if u == v:
                v += 1
        if u < n: # add edge (u, v)
            bu, bv = banks_numbered[u], banks_numbered[v]
            net.add_or_update_link(bu, bv, update_balance_sheets=False)
    homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
    return net


def from_unique_id_link_list(n, links, alpha, kappa):
    """
    Create network from list of links with unique bank ids and no gaps in ids.
    Example: [[1, 2], [3, 1]]
    """
    net = Network()
    banks_by_id = {}
    for _ in range(n):
        b = Bank()
        net.add_bank(b)
        banks_by_id[b.id_] = b
    for link in links:
        u = banks_by_id[link[0]]
        v = banks_by_id[link[1]]
        net.add_or_update_link(u, v, update_balance_sheets=False)
    homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
    return net


def from_adjacency_matrix(ad_mat):
    raise NotImplementedError()
