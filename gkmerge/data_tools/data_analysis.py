from gkmerge.data_tools.util import *


def contagion_extend(df_or_af_lst, cascade_threshold):
    """
    For a given list of defaulted fractions from various simulation runs
    calculates the mean contagion extend where a global cascade is defined
    accoring to cadcade_threshold.
    """
    return filtered_mean(df_or_af_lst, lambda df: df > cascade_threshold)


def cascade_steps(steps_lst, df_or_af_lst, cascade_threshold):
    return externally_filtered_mean(steps_lst, df_or_af_lst, lambda df: df > cascade_threshold)


def contagion_frequency(df_or_af_lst, cascade_threshold):
    """
    For a given list of defaulted fractions from various simulation runs
    calculates the contagion frequency among the runs, where a global cascade
    is defined accoring to cadcade_threshold.
    """
    return fraction(df_or_af_lst, lambda df: df > cascade_threshold)


def mean_degree(z_lst):
    return mean(z_lst)
