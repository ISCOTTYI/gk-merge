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
        self.balance_sheet = dict(
            assets_ib=0,
            assets_e=0,
            liabilities_ib=0,
            liabilities_e=0, # deposits
            provision=0, # used to compensate capital increase
            shock=0
        )
        self.temp_balance_sheet = None
        self.r_val = 0 # number of banks infected by self
        self.size = 0.0

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

    def update_state(self, sucs_weighted, recovery_rate, mode="simultaneous"):
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
            self._simultaneous_update(sucs_weighted, recovery_rate)
        elif mode == "sequential":
            self._sequential_update(sucs_weighted, recovery_rate)
        else:
            raise ValueError(f"Update mode '{mode}' is unknown!")
        return True

    def _simultaneous_update(self, sucs_weighted, recovery_rate):
        """
        Update insolvent bank in simultaneous update mode.
        Banks get updated in waves, therefore we set temp_states first and
        then simultaneously update the whole network with tempstates
        """
        self.temp_defaulted = True
        for suc, lend in sucs_weighted:
            # if bank was insolvent previous to this update round or was already
            # shocked to default in this round (has insolvent temp_bs) we skip
            temp_bs_set = bool(suc.temp_balance_sheet is not None)
            if not suc.is_solvent():
                continue
            # FIXME: If shock transmission depends on outstanding loss after default,
            # this if-clause should be removed! 
            if temp_bs_set and not suc.is_solvent(temp=True):
                continue
            # suc is solvent and either got no temp_bs or a solvent temp_bs
            # init temp_balance sheet if not yet set
            if not temp_bs_set:
                suc.temp_balance_sheet = dict(suc.balance_sheet)
            # transmit shock
            suc.temp_balance_sheet["shock"] += lend * (1 - recovery_rate)
            if not suc.is_solvent(temp=True):
                # r_val changed if self responsible for default of suc
                self.r_val += 1

    def _sequential_update(self, sucs_weighted, recovery_rate):
        """
        Update insolvent bank in sequential update mode.
        Directly set state and balance sheet. Banks are updated in arbitrary order
        """
        self.defaulted = True
        for suc, lend in sucs_weighted:
            if not suc.is_solvent():
                continue
            suc.balance_sheet["shock"] += lend * (1 - recovery_rate)
            if not suc.is_solvent():
                self.r_val += 1
    
    # def _non_zero_recovery(self, lend): # FIXME: ?
    #     # TODO: DEBUG CHECK
    #     if self.capital() > 0:
    #         print("something is wrong")
    #     asset_shortfall = abs(self.capital())
    #     bankruptcy_costs = self.balance_sheet["liabilities_ib"] / 2
    #     liability_share = lend / self.balance_sheet["liabilities_ib"]
    #     return min((asset_shortfall + bankruptcy_costs) * liability_share, lend)
    
    # def __eq__(self, o: object) -> bool:
    #     pass

    # def __hash__(self) -> int:
    #     pass

    # def __str__(self) -> str:
    #     pass
