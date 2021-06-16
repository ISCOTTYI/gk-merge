import logging
from gkmerge.bank import Bank

logger = logging.getLogger(__name__)

def add_link(bank_1, bank_2, weight=0):
    if not isinstance(bank_1, Bank) or not isinstance(bank_2, Bank):
        raise TypeError("Can only add a link between banks")
    bank_1.successors[bank_2] = weight
    bank_2.predecessors[bank_1] = weight

