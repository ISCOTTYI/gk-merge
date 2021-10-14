import numpy as np


def mean(lst):
    """
    Clears the given list of None and calculates the mean
    """
    lst = [elem for elem in lst if elem is not None]
    return np.mean(np.array(lst)) if len(lst) > 0 else 0


def std(lst):
    return np.std(np.array(lst)) if len(lst) > 0 else 0


def greater_than(val, cond=0):
    return bool(val > cond)


def filtered_mean(lst, filter_func):
    a = np.array(lst)
    a = a[filter_func(a)]
    return np.mean(a) if len(a) > 0 else 0


def externally_filtered_mean(lst, filter_lst, filter_func):
    """
    Returns the conditional mean of the list after clearing it from None
    E.g. a value in lst at pos i is counted to the mean if and only if
    condition(condition_lst[i]) is true. Give keyworded args of condition function as kwargs.
    """
    if len(lst) != len(filter_lst):
        raise ValueError("lst and condition_lst must be of the same length!")
    cond_corr_lst = []
    for i, elem in enumerate(lst):
        if filter_func(filter_lst[i]):
            cond_corr_lst.append(elem)
    cond_corr_lst = [elem for elem in cond_corr_lst if elem is not None]
    return np.mean(np.array(cond_corr_lst)) if len(cond_corr_lst) > 0 else 0


def fraction(lst, frac_func):
    lst = [elem for elem in lst if elem is not None]
    cond_cnt, tot_cnt = 0, 0
    for elem in lst:
        tot_cnt += 1
        if frac_func(elem):
            cond_cnt += 1
    return cond_cnt / tot_cnt if tot_cnt > 0 else 0
