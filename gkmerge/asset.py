import logging
import math

logger = logging.getLogger(__name__)

###################
#                 #
#   ASSET CLASS   #
#                 #
###################

class Asset():
    asset_cnt = 0

    def __init__(self, price=1):
       self.id_ = Asset.asset_cnt
       Asset.asset_cnt += 1
       self._price = price
       self.phi = 1 # devaluation factor
    
    @property
    def price(self):
        return self._price * self.phi
    
    def devaluate_exp(self, liquidated_fraction):
        alpha = 1.0536
        f = math.exp((-alpha) * liquidated_fraction)
        self.phi = f
        return f
    
    def devaluate_debug(self, liquidated_fraction):
        f = liquidated_fraction
        self.phi = f
        return f
