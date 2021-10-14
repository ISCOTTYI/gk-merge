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
            assets_e=0, # external assets NOT including common external asset
            assets_com=0, # common external asset among banks in network
            liabilities_ib=0,
            liabilities_e=0, # deposits
            # provision=0, # used to compensate capital increase
            shock=0, # interbank network shock
            shock_e=0 # shock to common external asset
        )
        self.temp_balance_sheet = None
        self.r_val = 0 # number of banks infected by self
        self.merge_state = 0
    
    def assets_tot(self, temp=False):
        if temp:
            bs = self.get_temp_balance_sheet()
        else:
            bs = self.balance_sheet
        return bs["assets_e"] + bs["assets_ib"] + bs["assets_com"]
    
    def liabilities_tot(self, temp=False):
        if temp:
            bs = self.get_temp_balance_sheet()
        else:
            bs = self.balance_sheet
        return bs["liabilities_e"] + bs["liabilities_ib"]
    
    def shock_tot(self, temp=False):
        if temp:
            bs = self.get_temp_balance_sheet()
        else:
            bs = self.balance_sheet
        return bs["shock_e"] + bs["shock"]
    
    def get_temp_balance_sheet(self):
        """
        Checks if temp_balance_sheet is set and if not set, sets it to current
        state of balance_sheet. Returns temp_balance_sheet
        """
        if self.temp_balance_sheet is None:
            self.temp_balance_sheet = dict(self.balance_sheet)
        return self.temp_balance_sheet

    def capital(self, temp=False):
        if temp and self.temp_balance_sheet is None:
            raise ValueError("temp_balance_sheet is None!")
        shocked_assets = self.assets_tot(temp=temp) - self.shock_tot(temp=temp)
        liabilities = self.liabilities_tot(temp=temp)
        return shocked_assets - liabilities

    def is_solvent(self, temp=False):
        """
        Bank is solvent when its capital is greater zero

        :return: True if bank is solvent, False else
        :rtype: bool
        """
        return bool(self.capital(temp=temp) > 0)
    
    def shocking_required(self):
        """
        If bank is defaulted, has insolvent balance_sheet or insolvent
        temp_balance_sheet, no further shocking is required. Hence,
        if True, self's balance_sheet is solvent and self got no temp_balance_sheet
        or a solvent temp_balance_sheet.
        """
        res = self.is_solvent()
        if self.temp_balance_sheet is not None:
            res = res and self.is_solvent(temp=True)
        return res and not self.defaulted

    def reset_temps(self):
        self.temp_defaulted = None
        self.temp_balance_sheet = None

    def aggregate_shock(self):
        bs = self.balance_sheet
        bs["shock_e"] = bs["assets_e"] + bs["assets_com"]

    def asset_com_shock(self, deprecation_factor, multiplicity=1, temp=False):
        if not self.shocking_required():
            return
        if temp:
            bs = self.get_temp_balance_sheet()
        else:
            bs = self.balance_sheet
        curr_a_com = bs["assets_com"] - bs["shock_e"]
        new_a_com = curr_a_com * (1 - deprecation_factor) ** multiplicity
        bs["shock_e"] += curr_a_com - new_a_com

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
            if not suc.shocking_required():
                continue
            # suc is solvent and either got no temp_bs or a solvent temp_bs
            # init temp_balance sheet if not yet set
            if suc.temp_balance_sheet is None:
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
            if not suc.shocking_required():
                continue
            suc.balance_sheet["shock"] += lend * (1 - recovery_rate)
            if not suc.is_solvent():
                self.r_val += 1
    
    # def __eq__(self, o: object) -> bool:
    #     pass

    # def __hash__(self) -> int:
    #     pass

    # def __str__(self) -> str:
    #     pass
