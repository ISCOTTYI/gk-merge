import logging
import random
import math
import numpy as np
# import functools
from itertools import permutations
from randomdict import RandomDict
from gkmerge.network import Network
from gkmerge.bank import Bank
from gkmerge.asset import Asset
from gkmerge.util import random_subset

logger = logging.getLogger(__name__)

__all__ = [
    "unlinked",
    "complete",
    "circular",
    "erdos_renyi",
    "fast_erdos_renyi",
    "bipartite_erdos_renyi",
    "fast_bipartite_erdos_renyi",
    "chung_lu",
    "from_unique_id_link_list",
    "init_balance_sheets_dcc",
    "init_balance_sheets_icc"
]


def init_balance_sheets_dcc(network, alpha, kappa, c):
    for b in network.banks:
        in_deg = network.in_deg_of(b)
        out_deg = network.out_deg_of(b)
        if in_deg + out_deg > 0:
            a_tot = (in_deg + out_deg + max(out_deg - in_deg, 0)) * 100 / 2 # linear relation
            a_ib = a_tot * alpha if in_deg > 0 else 0
            a_ib_per_pre = a_ib / in_deg if in_deg > 0 else 0
        else:
            a_tot = 100
            a_ib = 0
            a_ib_per_pre = 0
        a_not_ib = a_tot - a_ib # total non-interbank assets (external + common)
        a_com = a_not_ib * c
        b.balance_sheet["assets_e"] = a_not_ib - a_com
        b.balance_sheet["assets_com"] = a_com
        for pre in network.pres_of(b):
            network.add_or_update_link(pre, b, weight=a_ib_per_pre)
    for b in network.banks:
        a_tot = b.assets_tot()
        network.init_system_assets += a_tot
        l_ib = b.balance_sheet["liabilities_ib"]
        k = a_tot * kappa
        b.balance_sheet["liabilities_e"] = a_tot - l_ib - k


def init_balance_sheets_icc(network, alpha, kappa):
    a_tot = 100
    a_com = a_tot * alpha
    c = a_tot - a_com # cash
    k = a_tot * kappa
    l = a_tot - k
    for b in network.banks:
        deg = network.inv_deg_of(b)
        if deg > 0:
            w = a_com / deg
            b.balance_sheet["assets_e"] = c
            for a in network.invs_of(b):
                network.add_or_update_investment(b, a, investment=w) # sets a_com in balance sheets
        else:
            w = 0
            b.balance_sheet["assets_e"] = a_tot
        b.balance_sheet["liabilities_e"] = l
        network.init_system_assets += a_tot


def unlinked(n):
    """
    Create network with given number n of banks
    """
    net = Network()
    for _ in range(n):
        b = Bank()
        net.add_bank(b)
    return net


def complete(n, alpha=0, kappa=0, c=0):
    net = unlinked(n)
    for u, v in permutations(net.banks, 2):
        # balance_sheets all 0 and weights all 0 too -> no need to update balance_sheets
        net.add_or_update_link(u, v, update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def circular(n, alpha=0, kappa=0, c=0):
    net = unlinked(n)
    banks_lst = list(net.banks)
    for i in range(n):
        u = banks_lst[i]
        v = banks_lst[(i + 1) % n]
        net.add_or_update_link(u, v, update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def erdos_renyi(n, p, alpha=0, kappa=0, c=0):
    net = unlinked(n)
    for u, v in permutations(net.banks, 2):
        if random.random() < p:
            net.add_or_update_link(u, v, update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def bipartite_erdos_renyi(n, m, mu_b, alpha=0, kappa=0):
    """
    alpha is fraction of common external assets, kappa is capital fraction on total assets
    """
    net = Network()
    bd, b_ids = {}, np.arange(n)
    ad, a_ids = {}, np.arange(m)
    for i in b_ids:
        b = Bank()
        net.add_bank(b)
        bd[int(i)] = b
    for i in a_ids:
        a = Asset()
        net.add_ext_asset(a)
        ad[int(i)] = a
    # https://stackoverflow.com/questions/1208118/using-numpy-to-build-an-array-of-all-combinations-of-two-arrays
    comb = np.array(np.meshgrid(b_ids, a_ids)).T.reshape((n*m, 2))
    # https://stackoverflow.com/questions/14262654/numpy-get-random-set-of-rows-from-2d-array
    numb_of_invests = int(n * mu_b)
    res = comb[np.random.choice(comb.shape[0], numb_of_invests, replace=False), :]
    # np.random.shuffle(comb)
    # res = comb[:n*mu_b]
    for bid, aid in res:
        net.add_or_update_investment(bd[bid], ad[aid], update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_icc(net, alpha, kappa)
    return net


def fast_bipartite_erdos_renyi(n, m, mu_b, alpha=0, kappa=0):
    """
    V. Batagelj and Ulrik Brandes, "Efficient generation of large random networks",
    Phys Rev E 71, (2005)
    """
    net = Network()
    assets_numbered, banks_numbered = {}, {}
    for i in range(min(n, m)):
        b = Bank()
        a = Asset()
        net.add_bank(b)
        net.add_ext_asset(a)
        banks_numbered[i] = b
        assets_numbered[i] = a
    for i in range(min(n, m), max(n, m)):
        if n > m:
            b = Bank()
            net.add_bank(b)
            banks_numbered[i] = b
        else:
            a = Asset()
            net.add_ext_asset(a)
            assets_numbered[i] = a
    p = mu_b / m
    if p <= 0:
        init_balance_sheets_icc(net, alpha, kappa)
        return net
    u, v, logp = 0, -1, math.log(1.0 - p)
    while u < n:
        logr = math.log(1.0 - random.random())
        v = v + 1 + int(logr / logp)
        while u < n and m <= v:
            v = v - m
            u = u + 1
        if u < n:
            bu, av = banks_numbered[u], assets_numbered[v]
            net.add_or_update_investment(bu, av, update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_icc(net, alpha, kappa)
    return net


def fast_erdos_renyi(n, p, alpha=0, kappa=0, c=0):
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
        init_balance_sheets_dcc(net, alpha, kappa, c)
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
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def directed_barabasi_albert(n, m, d=0.5, io=0.05, alpha=0, kappa=0, c=0):
    """
    Scale-free graph with n nodes. During preferential attachment, new node is
    connected to m existing nodes. With probability d the added edge goes from
    new node to existing node (in-edge for existing node). With probability io
    new node is connected to existing node both ways. Due to this the number
    of edges will vary between networks.

    Average Degree: <k> = m
    Gamma Exponent in powerlaw: gamma = 3
    """
    if m < 1 or m >= n:
        raise ValueError(f"For barabasi albert network m >= 1 and m < n not m = {m}, n = {n}")
    net = complete(m + 1)
    # store nodes their in-deg + out-deg number of times
    node_selector = [b for b in net.banks for _ in range(net.in_deg_of(b) + net.out_deg_of(b))]
    n_curr = m + 1
    while n_curr < n:
        b = Bank()
        net.add_bank(b)
        n_curr += 1
        connect_to = random_subset(node_selector, m)
        for ctb in connect_to:
            r = random.random()
            if r < io:
                net.add_or_update_link(b, ctb)
                net.add_or_update_link(ctb, b)
                node_selector.extend([b, ctb] * 2)
            elif r < d:
                net.add_or_update_link(b, ctb)
                node_selector.extend([b, ctb])
            else:
                net.add_or_update_link(ctb, b)
                node_selector.extend([b, ctb])
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def chung_lu(n, z, gamma=3, alpha=0, kappa=0, c=0):
    net = Network()
    banks_numbered, bank_numbers = {}, np.arange(1, n + 1)
    for i in range(1, n + 1):
        b = Bank()
        net.add_bank(b)
        banks_numbered[i] = b
    p = 1 / (gamma - 1)
    ws = bank_numbers ** (- p) # np.array([i ** (- p) for i in bank_numbers])
    wsum = np.sum(ws)
    probs = ws / wsum
    links = np.random.choice(bank_numbers, size=int(2*n*z), p=probs).reshape(-1, 2)
    for u, v in links:
        bu, bv = banks_numbered[u], banks_numbered[v]
        while net.is_suc(bu, bv) or u == v:
            # print(".", end="")
            v = (v % n) + 1
            bv = banks_numbered[v]
        net.add_or_update_link(bu, bv, update_balance_sheets=False)
    # while net.number_of_links < z * n:
    #     u, v = np.random.choice(bank_numbers, size=2, replace=False, p=probs)
    #     bu, bv = banks_numbered[u], banks_numbered[v]
    #     net.add_or_update_link(bu, bv, update_balance_sheets=False)
    if alpha > 0 or kappa > 0:
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def fast_chung_lu(n, d, gamma=3, alpha=0, kappa=0, c=0):
    """
    [1] Miller, Joel C., and Aric Hagberg. Springer (2011)
    [2] Fasino, D., Tonetto, A., & Tudisco, F. arXiv:1910.11341 (2019)
    """
    net = Network()
    banks_numbered, bank_numbers = {}, range(n)
    for i in range(n):
        b = Bank()
        net.add_bank(b)
        banks_numbered[i] = b
    if gamma <= 2:
        raise ValueError(f"gamma must be > 2, not {gamma}!")
    if d <= 2:
        raise ValueError(f"d must be > 2, not {d}!")
    # construct weight list [2]
    m = math.sqrt((d * n) / 2)
    p = 1 / (gamma - 1)
    c = (1 - p) * d * (n ** p)
    i0 = (c / m) ** (1 / p) - 1
    ws = [c / ((i + i0) ** p) for i in range(n)] # decreasing order
    wsum = sum(ws)
    # create chung-lu graph [1]
    for u in range(n):
        v = 0
        if v == u: # no self-loops
            v += 1
        p_cl = min(ws[u] * ws[v] / wsum, 1)
        while v < n and p_cl > 0:
            if p_cl != 1:
                r1 = random.random()
                logr, logp = math.log(r1), math.log(1 - p_cl)
                v = v + int(logr / logp)
            if v == u:
                v += 1
            if v < n:
                r2 = random.random()
                q_cl = min(ws[u] * ws[v] / wsum, 1)
                if r2 < q_cl / p_cl: # add edge (u, v)
                    bu, bv = banks_numbered[u], banks_numbered[v]
                    net.add_or_update_link(bu, bv, update_balance_sheets=False)
                p_cl = q_cl
                v += 1
    if alpha > 0 or kappa > 0:
        # homo_cap = seed_homogenous_balance_sheets(net, alpha, kappa)
        init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def from_unique_id_link_list(n, links, alpha=0, kappa=0, c=0):
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
    init_balance_sheets_dcc(net, alpha, kappa, c)
    return net


def from_adjacency_matrix(ad_mat):
    raise NotImplementedError()
