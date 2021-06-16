import logging
from collections import deque, Counter
from itertools import islice
from typing import OrderedDict
import numpy as np
from gkmerge.bank import Bank

logger = logging.getLogger(__name__)

#####################
#                   #
#   NETWORK CLASS   #
#                   #
#####################

class Network():
    def __init__(self, banks=None): # banks holds bank: bank
        if banks is None:
            self.banks = {}
        else:
            self.banks = banks
        self.simultaneous_cascade_steps = None
        self.merge_round = 0

    @property
    def number_of_banks(self):
        return len(self.banks)

    @property
    def banks_by_id(self):
        return {b.id_: b for b in self.banks}

    @property
    def banks_defaulted(self):
        return {b: b.defaulted for b in self.banks}

    @property
    def links(self):
        return [(b, suc) for b in self.banks for suc, weight in b.successors.items()]
    
    @property
    def links_by_id(self):
        return [(b.id_, suc.id_) for b in self.banks for suc, weight in b.successors.items()]


    @property
    def adjacency_matrix(self):
        banks_index = OrderedDict({b: i for i, b in enumerate(self.banks)})
        matrix = []
        for b in banks_index:
            matrix_row_i = [0] * len(banks_index)
            for suc, weight in b.successors.items():
                matrix_row_i[banks_index[suc]] = weight
            matrix.append(matrix_row_i)
        return matrix
    
    def add_bank(self, bank, handle_links=True):
        """
        Add a bank to the network. If handle_links is True, add pres and sucs
        of added bank if neccessary and make sure links are correct with the
        pres and sucs.
        """
        if not isinstance(bank, Bank):
            raise TypeError(f"Can only add Banks, not type {type(bank)}")
        if bank in self.banks:
            logger.warning(f"Bank with id {bank.id_} is already in network!")

        self.banks[bank] = bank
        
        if not handle_links:
            return
        for pre, weight in bank.predecessors.items():
            if pre not in self.banks:
                self.add_bank(pre)
            if bank not in pre.successors:
                pre.successors[bank] = weight
        for suc, weight in bank.successors.items():
            if suc not in self.banks:
                self.add_bank(suc)
            if bank not in suc.predecessors:
                suc.predecessors[bank] = weight

    def add_banks_from(self, banks, handle_links=True):
        for b in banks:
            self.add_bank(b, handle_links=handle_links)

    def remove_bank(self, bank, handle_links=True):
        if not bank in self.banks:
            raise ValueError(f"Bank with id {bank.id_} is not in network")
        
        del self.banks[bank]

        if not handle_links:
            return
        for pre in bank.predecessors:
            if pre not in self.banks:
                continue
            del pre.successors[bank]
        for suc in bank.successors:
            if suc not in self.banks:
                continue
            del suc.predecessors[bank]

    def remove_banks_from(self, banks, handle_links=True):
        for b in banks:
            self.remove_bank(b, handle_links=handle_links)

    def shock_random(self):
        # https://stackoverflow.com/questions/32802869/selecting-a-random-value-from-dictionary-in-constant-time-in-python-3
        b = next(islice(self.banks.keys(), np.random.randint(0, len(self.banks)), None))
        b.aggregate_shock()
        return b

    def shock_largest(self):
        b = self.get_largest()
        b.aggregate_shock()
        return b
    
    def shock_id(self, id_):
        b = self.banks_by_id[id_]
        b.aggregate_shock()
        return b

    def cascade(self, init_shock_bank, mode="simultaneous"):
        """
        Calculate default cascade upon initial shock of bank init_shock_bank.
        Update mode specifies order of bank updates:
            - 'simultaneous':   Update in timesteps. In step i + 1 only successors of
                                banks defaulted in step i can default
            - 'sequential':     Update order arbitrary. Much faster.
        """
        if mode ==  "simultaneous":
            self.simultaneous_cascade_steps = 0
            self._simultaneous_cascade()
        elif mode == "sequential":
            self._sequential_cascade(init_shock_bank)
        else:
            raise ValueError(f"Update mode '{mode}' is unknown!")
        
    def _simultaneous_cascade(self):
        something_changed = True
        steps = 0
        while(something_changed):
            something_changed = False
            for b in self.banks:
                # NOTE: if order of statements in "or" is changed, update_state will not evaluate
                # once something_changed is True
                something_changed = b.update_state(mode="simultaneous") or something_changed
            if something_changed:
                for b in self.banks:
                    if b.temp_defaulted is not None:
                        b.defaulted = b.temp_defaulted
                    if b.temp_balance_sheet is not None:
                        b.balance_sheet = b.temp_balance_sheet
                    b.reset_temps()
                steps += 1
        self.simultaneous_cascade_steps = steps

    def _sequential_cascade(self, init_shock_bank):
        """
        Default cascade with sequential update mode.
        """
        stack = deque()
        on_stack = {b: False for b in self.banks}
        # Init stack
        stack.append(init_shock_bank)
        on_stack[init_shock_bank] = True
        while(stack):
            b = stack.pop()
            on_stack[b] = False
            if b.update_state(mode="sequential"):
                for suc in b.successors:
                    if not suc.defaulted and not on_stack[suc]:
                        stack.append(suc)
                        on_stack[suc] = True

    def get_largest(self):
        return max(self.banks, key=lambda b: b.size)

    def defaulted_fraction(self):
        c = Counter((b.defaulted for b in self.banks))
        return c[True] / self.number_of_banks
    
    def z(self):
        return sum((len(b.successors) for b in self.banks)) / self.number_of_banks
