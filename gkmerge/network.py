import logging
from collections import deque, Counter
from randomdict import RandomDict
# from itertools import islice
from typing import OrderedDict
from gkmerge.bank import Bank
from gkmerge.asset import Asset
from gkmerge.util import sample_unique_pair, sample_except, random_pairs

logger = logging.getLogger(__name__)

#####################
#                   #
#   NETWORK CLASS   #
#                   #
#####################


def print_infos(net, ad_mat=True, neib_info=False):
    for b in net.banks:
        print(f"{b.id_}\n  {b.balance_sheet}, K={b.capital()}")
        if neib_info:
            print(f"  Out neib: {[str(n[0].id_) + ': ' + str(n[1]) for n in net.sucs_of(b, weight=True)]}")
            print(f"  In neib: {[str(n[0].id_) + ': ' + str(n[1]) for n in net.pres_of(b, weight=True)]}")


def print_infos_icc(net):
    print_infos(net, ad_mat=False)
    print("\nBanks and their investments")
    for b, ad in net._bank_invest.items():
        print(f"{b.id_}: \n {[(a.id_, w) for a, w in ad.items()]}\n")
    print("\nAssets and their investors")
    for a, bd in net._asset_invest.items():
        print(f"{a.id_}: {[b.id_ for b in bd]}")
    print("\n")


class Network():
    def __init__(self, input=None): # banks is dict-like and holds bank: bank
        self.banks = RandomDict()
        self.number_of_links = 0
        self._pres = {} # stores {bank: {pre_of_bank: weight, ...}, ...}
        self._sucs = {} # stores {bank: {suc_of_bank: weight, ...}, ...}
        
        self.ext_assets = RandomDict() # stores {asset: price} ???
        self.number_of_investments = 0
        self._bank_invest = {} # stores {bank: {ext_a: investment}, ...}, ...}
        self._asset_invest = {} # stores {ext_a: {bank: investment}, ...}, ...}

        self.simultaneous_cascade_steps = None
        self.merge_round = 0
        self._shmp_pairs = None
        self.df_over_time = []
        self.init_system_assets = 0 # TODO: REFACTOR THIS NAME!!!
        self.defaulted_system_assets = 0 # TODO: REFACTOR THIS NAME!!!
        self.system_assets_over_time = [] # TODO: REFACTOR THIS NAME!!!

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
        return [(b, suc) for b in self._sucs for suc in self._sucs[b]]
    
    @property
    def links_by_id(self):
        return [(b.id_, suc.id_) for b in self._sucs for suc in self._sucs[b]]

    @property
    def adjacency_matrix(self):
        banks_index = OrderedDict({b: i for i, b in enumerate(self.banks)})
        matrix = []
        for b in banks_index:
            matrix_row_i = [None] * len(banks_index)
            for suc, weight in self._sucs[b].items():
                matrix_row_i[banks_index[suc]] = weight
            matrix.append(matrix_row_i)
        return matrix
    
    def add_bank(self, bank):
        """
        Add a bank to the network. If handle_links is True, add pres and sucs
        of added bank if neccessary and make sure links are correct with the
        pres and sucs.
        """
        if not isinstance(bank, Bank):
            raise TypeError(f"Can only add Banks, not type {type(bank)}")
        if bank in self.banks:
            raise ValueError(f"Bank with id {bank.id_} is already in network!")
        self.banks[bank] = bank
        self._sucs[bank] = {}
        self._pres[bank] = {}
        self._bank_invest[bank] = {}

    def add_banks_from(self, banks):
        for b in banks:
            self.add_bank(b)

    def remove_bank(self, bank, update_balance_sheets=True):
        try:
            del self.banks[bank]
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
        for pre, w in self.pres_of(bank, weight=True):
            if update_balance_sheets:
                pre.balance_sheet["liabilities_ib"] -= w
            del self._sucs[pre][bank]
        del self._pres[bank]
        for suc, w in self.sucs_of(bank, weight=True):
            if update_balance_sheets:
                suc.balance_sheet["assets_ib"] -= w
            del self._pres[suc][bank]
        del self._sucs[bank]
        for a in self.invs_of(bank):
            del self._asset_invest[a][bank]
        del self._bank_invest[bank]
    
    def remove_banks_from(self, banks):
        for b in banks:
            self.remove_bank(b)
    
    def add_ext_asset(self, asset):
        if not isinstance(asset, Asset):
            raise TypeError(f"Can only add Assets, not type {type(asset)}")
        if asset in self.ext_assets:
            raise ValueError(f"Asset with id {asset.id_} is already in network!")
        self.ext_assets[asset] = asset # ???
        self._asset_invest[asset] = {}
    
    def remove_ext_asset(self, asset, update_balance_sheets=True):
        try:
            del self.ext_assets[asset]
        except KeyError:
            raise ValueError(f"Asset with id {asset.id_} is not in network!")
        for b, inv in self._asset_invest[asset]:
            if update_balance_sheets:
                b.balance_sheet["assets_com"] -= inv
            del self._bank_invest[b][asset]
        del self._asset_invest[asset]

    def add_or_update_link(self, u, v, weight=0, update_balance_sheets=True):
        """
        Adds a link or updates its weight if link already in network.
        If update_balance_sheets is True, interbank positions in balance sheets
        will also be updated.
        """
        if u == v:
            raise ValueError("Selfloops are not supported!")
        try:
            u_sucs = self._sucs[u] # KeyError if banks not in the network
            v_pres = self._pres[v]
            if update_balance_sheets:
                curr_weight = 0
                if v in self._sucs[u]:
                    curr_weight = self._sucs[u][v]
                u.balance_sheet["liabilities_ib"] += weight - curr_weight
                v.balance_sheet["assets_ib"] += weight - curr_weight
            if not v in u_sucs: # link already in network
                self.number_of_links += 1
            u_sucs[v] = weight
            v_pres[u] = weight
        except KeyError:
            raise ValueError(f"Bank(s) from link ({u.id_}, {v.id_}) not in network!")
    
    add_link = add_or_update_link
    
    def remove_link(self, u, v, update_balance_sheets=True):
        try:
            if update_balance_sheets:
                weight = self._sucs[u][v]
                u.balance_sheet["liabilities_ib"] -= weight
                v.balance_sheet["assets_ib"] -= weight
            del self._sucs[u][v]
            del self._pres[v][u]
        except KeyError:
            raise ValueError(f"Link ({u.id_}, {v.id_}) is not in network!")
    
    def get_link_weight(self, u, v):
        try:
            return self._sucs[u][v]
        except KeyError:
            raise ValueError(f"Link ({u.id_}, {v.id_}) is not in network!")
    
    def add_or_update_investment(self, bank, asset, investment=0, update_balance_sheets=True):
        try:
            b_inv = self._bank_invest[bank]
            a_inv = self._asset_invest[asset]
            if update_balance_sheets:
                curr_inv = 0
                if asset in self._bank_invest[bank]:
                    curr_inv = self._bank_invest[bank][asset]
                bank.balance_sheet["assets_com"] += investment - curr_inv
            if not asset in b_inv:
                self.number_of_investments += 1
            b_inv[asset] = investment
            a_inv[bank] = investment
        except KeyError:
            raise ValueError(f"Asset with id {asset.id_} or bank with id {bank.id_} not in network!")

    def get_inv_weight(self, bank, asset):
        try:
            return self._bank_invest[bank][asset]
        except KeyError:
            raise ValueError(f"Asset with id {asset.id_} or bank with id {bank.id_} not in network!")

    def sucs_of(self, bank, weight=False):
        try:
            if weight:
                return self._sucs[bank].items()
            return self._sucs[bank].keys()
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def pres_of(self, bank, weight=False):
        try:
            if weight:
                return self._pres[bank].items()
            return self._pres[bank].keys()
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def invs_of(self, bank, weight=False):
        try:
            if weight:
                return self._bank_invest[bank].items()
            return self._bank_invest[bank].keys()
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
        
    def is_suc(self, bank, suc):
        try:
            return (suc in self._sucs[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def is_pre(self, bank, pre):
        try:
            return (pre in self._pres[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")

    def is_inv(self, bank, asset):
        try:
            return (asset in self._bank_invest[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def out_deg_of(self, bank):
        try:
            return len(self._sucs[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
        
    def in_deg_of(self, bank):
        try:
            return len(self._pres[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def inv_deg_of(self, bank):
        try:
            return len(self._bank_invest[bank])
        except KeyError:
            raise ValueError(f"Bank with id {bank.id_} is not in network!")
    
    def asset_deg_of(self, asset):
        try:
            return len(self._asset_invest[asset])
        except KeyError:
            raise ValueError(f"Asset with id {asset.id_} is not in network!")
    
    def liquidated_fraction(self, asset):
        try:
            tc, lc = 0, 0
            for b, w in self._asset_invest[asset].items():
                if b.defaulted:
                    lc += w
                tc += w
            return lc / tc
        except KeyError:
            raise ValueError(f"Asset with id {asset.id_} is not in network!")

    def get_largest(self):
        # if all banks are equal size returns the first in iterator
        return max(self.banks, key=lambda b: b.merge_state)
    
    def get_highest_in_deg(self):
        return max(self.banks, key=lambda b: self.in_deg_of(b))

    def get_highest_out_deg(self):
        return max(self.banks, key=lambda b: self.out_deg_of(b))
    
    def get_kth_highest_in_deg(self, k):
        return sorted(list(self.banks), key=lambda b: self.in_deg_of(b))[-k]
    
    def get_kth_highest_out_deg(self, k):
        return sorted(list(self.banks), key=lambda b: self.out_deg_of(b))[-k]

    def shock_random(self):
        # https://stackoverflow.com/questions/32802869/selecting-a-random-value-from-dictionary-in-constant-time-in-python-3
        # b = next(islice(self.banks.keys(), np.random.randint(0, len(self.banks)), None))
        b = self.banks.random_key()
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
    
    def shock_max_in_deg(self):
        b = self.get_highest_in_deg()
        b.aggregate_shock()
        return b

    def shock_random_asset(self, phi_new):
        a = self.ext_assets.random_key()
        # print(f"Asset {a.id_} initially shocked!")
        phi_curr = a.phi
        a.phi = phi_new
        for b, w in self._asset_invest[a].items():
            if not b.shocking_required():
                continue
            new_shock = w * phi_curr - w * phi_new
            # print(f"bank {b.id_} got new shock {new_shock} due to initial asset shock")
            b.balance_sheet["shock_e"] += new_shock
        return a

    def cascade(
        self, init_shock_bank, mode="simultaneous",
        recovery_rate=0, deprecation_factor=0, record_profiles=False
    ):
        """
        Calculate default cascade upon initial shock of bank init_shock_bank.
        Update mode specifies order of bank updates:
            - 'simultaneous':   Update in timesteps. In step i + 1 only successors of
                                banks defaulted in step i can default
            - 'sequential':     Update order arbitrary. Much faster.
        """
        if mode ==  "simultaneous":
            self.simultaneous_cascade_steps = 0
            self._simultaneous_cascade(recovery_rate, deprecation_factor, record_profiles)
        elif mode == "sequential":
            self._sequential_cascade(
                init_shock_bank, recovery_rate, deprecation_factor, record_profiles
            )
        else:
            raise ValueError(f"Update mode '{mode}' is unknown!")
        
    def _simultaneous_cascade(self, recovery_rate, deprecation_factor, record_profiles):
        something_changed = True
        steps = 0
        if record_profiles:
            self.system_assets_over_time.append(self.init_system_assets)
        while(something_changed):
            # ab = self.get_largest()
            # print(ab.shock_tot())
            something_changed = False
            newly_defaulted = 0
            for b in self.banks:
                # NOTE: if order of statements in "or" is changed, update_state
                # will not evaluate once something_changed is True
                b_changed = b.update_state(
                    self.sucs_of(b, weight=True), recovery_rate, mode="simultaneous"
                )
                something_changed = (b_changed or something_changed)
                if b_changed:
                    newly_defaulted += 1
                    self.defaulted_system_assets += b.assets_tot()
            if something_changed:
                for b in self.banks:
                    # perform external shock to temp_balance_sheets
                    if deprecation_factor > 0:
                        b.asset_com_shock(
                            deprecation_factor, multiplicity=newly_defaulted, temp=True
                        )
                    # apply changes
                    if b.temp_defaulted is not None:
                        b.defaulted = b.temp_defaulted
                    if b.temp_balance_sheet is not None:
                        b.balance_sheet = b.temp_balance_sheet
                    b.reset_temps()
                steps += 1
                if record_profiles:
                    curr_system_assets = self.init_system_assets - self.defaulted_system_assets
                    self.system_assets_over_time.append(curr_system_assets)
                    self.df_over_time.append(self.defaulted_fraction())
        self.simultaneous_cascade_steps = steps

    def _sequential_cascade(self, init_shock_bank, recovery_rate, deprecation_factor, record_profiles):
        """
        Default cascade with sequential update mode.
        """
        if deprecation_factor > 0:
            raise NotImplementedError()
        stack = deque()
        on_stack = {b: False for b in self.banks}
        # Init stack
        stack.append(init_shock_bank)
        on_stack[init_shock_bank] = True
        while(stack):
            b = stack.pop()
            on_stack[b] = False
            if b.update_state(self.sucs_of(b, weight=True), recovery_rate, mode="sequential"):
                for suc in self.sucs_of(b):
                    if not suc.defaulted and not on_stack[suc]:
                        stack.append(suc)
                        on_stack[suc] = True
    
    def reset_cascade(self):
        for b in self.banks:
            b.defaulted = False
            b.reset_temps()
            b.r_val = 0
            b.balance_sheet["shock"] = 0
            b.balance_sheet["shock_e"] = 0
        for a in self.ext_assets:
            a.phi = 1
        self.simultaneous_cascade_steps = None
        self.defaulted_system_assets = 0
        self.system_assets_over_time = []
        self.df_over_time = []
    
    def icc_cascade(self):
        something_changed = True
        step = 0
        self.system_assets_over_time.append(self.init_system_assets)
        while something_changed:
            # ab = self.get_largest()
            # print(ab.shock_tot())
            # print("\n--- NEW ROUND ---\n")
            # print_infos_icc(self)
            something_changed = False
            step += 1
            update_assets = set()
            for b in self.banks:
                b_changed = not b.is_solvent() and not b.defaulted
                something_changed = b_changed or something_changed
                if b_changed:
                    # print(f"{b.id_} defaulted")
                    b.defaulted = True
                    update_assets.update(self.invs_of(b))
                    self.defaulted_system_assets += b.assets_tot()
            for a in update_assets:
                self._devaluate_asset(a)
            current_system_assets = self.init_system_assets - self.defaulted_system_assets
            self.system_assets_over_time.append(current_system_assets)
        self.simultaneous_cascade_steps = step
            
    def _devaluate_asset(self, asset):
        phi_curr = asset.phi
        phi_new = asset.devaluate_exp(self.liquidated_fraction(asset)) # DEBUG
        # print(f"asset {asset.id_}: phi = {phi_curr} to {phi_new}, lf = {self.liquidated_fraction(asset)}")
        for b, w in self._asset_invest[asset].items():
            if not b.shocking_required():
                continue
            new_shock = w * phi_curr - w * phi_new
            # print(new_shock / b.assets_tot())
            # print(f"  bank {b.id_} got new shock {new_shock}")
            b.balance_sheet["shock_e"] += new_shock

    def icc_merge(self, acquiring, acquired):
        if acquiring == acquired:
            raise ValueError("Bank can not acquire itself!")
        # external balance sheet quantities are added
        ing_bs, ed_bs = acquiring.balance_sheet, acquired.balance_sheet
        ing_bs["assets_e"] += ed_bs["assets_e"]
        ing_bs["liabilities_e"] += ed_bs["liabilities_e"]
        ing_bs["shock"] += ed_bs["shock"]
        ing_bs["shock_e"] += ed_bs["shock_e"]
        # handle external asset investments
        for a, w in self.invs_of(acquired, weight=True):
            new_w = w
            if self.is_inv(acquiring, a):
                new_w += self.get_inv_weight(acquiring, a)
            self.add_or_update_investment(acquiring, a, investment=new_w)
        acquiring.merge_state += acquired.merge_state + 1
        self.remove_bank(acquired)
        self.merge_round += 1

    def merge(self, acquiring, acquired):
        """
        Merge two banks in the network. Merge is interpreted as the acquisition
        of one bank by the other.
        """
        if acquiring == acquired:
            raise ValueError("Bank can not acquire itself!")
        # remember total assets of merging banks
        a_tot = acquiring.assets_tot() + acquired.assets_tot()
        # external balance sheet quantities are simply added
        ing_bs, ed_bs = acquiring.balance_sheet, acquired.balance_sheet
        ing_bs["assets_e"] += ed_bs["assets_e"]
        ing_bs["assets_com"] += ed_bs["assets_com"]
        ing_bs["liabilities_e"] += ed_bs["liabilities_e"]
        ing_bs["shock"] += ed_bs["shock"]
        ing_bs["shock_e"] += ed_bs["shock_e"]
        # ing_bs["provision"] += ed_bs["provision"]
        # handle interbank links
        for suc, w in self.sucs_of(acquired, weight=True):
            # TODO: maybe use try catch instead as add_link checks for selfloops
            if suc == acquiring:
                continue
            new_w = w
            if self.is_suc(acquiring, suc):
                new_w += self.get_link_weight(acquiring, suc)
            self.add_or_update_link(acquiring, suc, weight=new_w)
        for pre, w in self.pres_of(acquired, weight=True):
            if pre == acquiring:
                continue
            new_w = w
            if self.is_pre(acquiring, pre):
                new_w += self.get_link_weight(pre, acquiring)
            self.add_or_update_link(pre, acquiring, weight=new_w)
        acquiring.merge_state += acquired.merge_state + 1
        self.remove_bank(acquired)
        # correct total system assets
        self.init_system_assets -= a_tot - acquiring.assets_tot()
        self.merge_round += 1

    def random_merge(self, rule, icc=False, **kwargs):
        """
        Merge rules for random are:
            - "random": Fully randomly select merge parties
            - "vertical": Largest bank acquires randomly selected smaller bank
            - "semihorizontal": Only small banks may merge
        """
        acquiring, acquired = self._sample_banks_for_merge(rule, **kwargs)
        if icc:
            self.icc_merge(acquiring, acquired)
        else:
            self.merge(acquiring, acquired)
    
    def _sample_banks_for_merge(self, rule, **kwargs):
        """
        Returns a tuple of banks.
        """
        if rule == "random":
            b, d = sample_unique_pair(self.banks)
            return b, d
        if rule == "vertical":
            if "aquiring_bank" in kwargs:
                lb = kwargs["aquiring_bank"]
            else:
                lb = self.get_largest()
            b = sample_except(self.banks, lb)
            return lb, b # when passed to merge lb is acquiring
        if rule == "semihorizontal":
            if self._shmp_pairs is None:
                self._shmp_pairs = random_pairs(self.banks)
            if len(self._shmp_pairs) == 0:
                raise ValueError("Can only perform semihorizontal if there are unmerged banks!")
            b, d = self._shmp_pairs.pop()
            return b, d
        raise ValueError(f"Unknown merge rule {rule}!")

    def defaulted_fraction(self):
        c = Counter((b.defaulted for b in self.banks))
        return c[True] / self.number_of_banks
    
    def defaulted_asset_fraction(self):
        ia = self.init_system_assets
        return self.defaulted_system_assets / ia if ia > 0 else 0
    
    def z(self):
        """
        Mean in-/out-degree of the network.
        """
        return sum((self.out_deg_of(b) for b in self.banks)) / self.number_of_banks
    
    def mu_b(self):
        """
        Mean investment-degree of network.
        """
        return sum((self.inv_deg_of(b) for b in self.banks)) / self.number_of_banks
    
    def mu_a(self):
        """
        Mean asset-degree of network.
        """
        return sum((self.asset_deg_of(a) for a in self.ext_assets)) / len(self.ext_assets)
    
    def in_deg_distr(self):
        in_deg_gen = (self.in_deg_of(b) for b in self.banks)
        c = Counter(in_deg_gen)
        return list(c.keys()), list(c.values())
    
    def out_deg_distr(self):
        out_deg_gen = (self.out_deg_of(b) for b in self.banks)
        c = Counter(out_deg_gen)
        return list(c.keys()), list(c.values())

    def inv_deg_distr(self):
        inv_deg_gen = (self.inv_deg_of(b) for b in self.banks)
        c = Counter(inv_deg_gen)
        return list(c.keys()), list(c.values())
    
    def merge_state_distr(self):
        ms_gen = (b.merge_state for b in self.banks)
        c = Counter(ms_gen)
        return c
        # return list(c.keys()), list(c.values())
    
    # def __str__(self) -> str:
    #     pass
