import logging

logger = logging.getLogger(__name__)

##################
#                #
#   BANK CLASS   #
#                #
##################

class Bank():
    bank_count = 0

    def __init__(self):
        self.id_ = Bank.bank_count
        Bank.bank_count += 1

        self.defaulted = False
        self.temp_defaulted = None
        self.r_val = 0 # number of banks infected by self

        self.balance_sheet = dict(
            assets_ib=0,
            assets_e=0,
            liabilities_ib=0,
            liabilities_e=0, # deposits
            provision=0, # used to compensate capital increase
            shock=0
        )

        self.temp_balance_sheet = None
        self.predecessors = dict() # holds [predecessor bank]: [link weight]
        self.successors = dict() # holds [successor bank]: [link weight]

        self.size = 0.0

    @property
    def predecessors_by_id(self):
        return {pre.id_: w for pre, w in self.predecessors.items()}

    @property
    def successors_by_id(self):
        return {suc.id_: w for suc, w in self.successors.items()}

    def capital(self, temp=False):
        if temp:
            if self.temp_balance_sheet is not None:
                bs = self.temp_balance_sheet
            else:
                raise ValueError("temp_balance_sheet is None!")
        else:
            bs = self.balance_sheet
        assets = bs["assets_ib"] + bs["assets_e"] - bs["shock"]
        liabilities = bs["liabilities_ib"] + bs["liabilities_e"]
        return assets - liabilities - bs["provision"]

    def is_solvent(self, temp=False):
        """
        Bank is solvent when its capital is greater zero

        :return: True if bank is solvent, False else
        :rtype: bool
        """
        return bool(self.capital(temp=temp) > 0)

    def reset_temps(self):
        self.temp_defaulted = None
        self.temp_balance_sheet = None

    def aggregate_shock(self):
        self.balance_sheet["shock"] = self.balance_sheet["assets_e"]

    def update_state(self, mode="simultaneous"):
        """
        Update banks state if required and propagate corresponding shock to successors.
        """
        if self.defaulted:
            # defaulted bank no longer updated
            return False
        if self.is_solvent():
            # no state update required
            return False

        # bank insolvent, update it and its successors
        if mode == "simultaneous":
            self._simultaneous_update()
        elif mode == "sequential":
            self._sequential_update()
        else:
            raise ValueError(f"Update mode '{mode}' is unknown!")
        return True

    def _simultaneous_update(self):
        """
        Update insolvent bank in simultaneous update mode.
        Banks get updated in waves, therefore we set temp_states first and
        then simultaneously update the whole network with tempstates
        """
        self.temp_defaulted = True
        for suc, lend in self.successors.items():
            # if bank was insolvent previous to this update round or was already
            # shocked to default in this round (has insolvent temp_bs) we skip
            temp_bs_set = bool(suc.temp_balance_sheet is not None)
            if not suc.is_solvent():
                continue
            if temp_bs_set and not suc.is_solvent(temp=True):
                continue
            # suc is solvent and either got no temp_bs or a solvent temp_bs
            # init temp_balance sheet if not yet set
            if not temp_bs_set:
                suc.temp_balance_sheet = dict(suc.balance_sheet)
            suc.temp_balance_sheet["shock"] += lend
            if not suc.is_solvent(temp=True):
                # r_val changed if self responsible for default of suc
                self.r_val += 1

    def _sequential_update(self):
        """
        Update insolvent bank in sequential update mode.
        Directly set state and balance sheet. Banks are updated in arbitrary order
        """
        self.defaulted = True
        for suc, lend in self.successors.items():
            if not suc.is_solvent():
                continue

            suc.balance_sheet["shock"] += lend

            if not suc.is_solvent():
                self.r_val += 1

    def acquire(self, acquired):
        if self == acquired:
            raise ValueError("Bank can not acquire itself!")
        if not isinstance(acquired, Bank):
            raise TypeError(f"Banks can only acquire other banks not type {type(acquired)}!")
        # interbank assets and liabilites and predecessor and successor dicts
        if acquired in self.successors:
            self.balance_sheet["liabilities_ib"] -= self.successors[acquired]
            del self.successors[acquired]
        for b, weight in acquired.predecessors.items():
            if b == self:
                continue
            if b in self.predecessors:
                self.predecessors[b] += weight
                b.successors[self] += weight # redirect link b -> acquired to acquiring
            else:
                self.predecessors[b] = weight
                b.successors[self] = weight # redirect link b -> acquired to acquiring
            del b.successors[acquired]
            self.balance_sheet["assets_ib"] += weight
        if acquired in self.predecessors:
            self.balance_sheet["assets_ib"] -= self.predecessors[acquired]
            del self.predecessors[acquired]
        for b, weight in acquired.successors.items():
            if b == self:
                continue
            if b in self.successors:
                self.successors[b] += weight
                b.predecessors[self] += weight
            else:
                self.successors[b] = weight
                b.predecessors[self] = weight
            del b.predecessors[acquired]
            self.balance_sheet["liabilities_ib"] += weight
        # external balance sheet quantities
        self.balance_sheet["assets_e"] += acquired.balance_sheet["assets_e"]
        self.balance_sheet["liabilities_e"] += acquired.balance_sheet["liabilities_e"]
        self.balance_sheet["shock"] += acquired.balance_sheet["shock"]
        self.balance_sheet["provision"] += acquired.balance_sheet["provision"]
