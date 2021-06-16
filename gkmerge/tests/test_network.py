import unittest
from gkmerge.bank import Bank
from gkmerge.network import Network
from gkmerge.util import add_link

class TestNetwork(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_number_of_banks(self):
        banks = {}
        for _ in range(3):
            b = Bank()
            banks[b] = b
        N = Network(banks=banks)
        self.assertEqual(N.number_of_banks, 3)

    def test_add_bank(self):
        b0, b1, b2, b3, b4 = Bank(), Bank(), Bank(), Bank(), Bank()
        b1.predecessors[b0] = 0
        b1.predecessors[b3] = 0
        b1.successors[b2] = 0
        b1.successors[b4] = 0
        banks = {b0: b0, b2: b2}
        N = Network(banks=banks)

        N.add_bank(b1)
        
        self.assertDictEqual({b0: b0, b1: b1, b2: b2, b3: b3, b4: b4}, N.banks)
        self.assertDictEqual({b1: 0}, b0.successors)
        self.assertDictEqual({b1: 0}, b3.successors)
        self.assertDictEqual({b1: 0}, b2.predecessors)
        self.assertDictEqual({b1: 0}, b4.predecessors)

    def test_shock_random(self):
        b0, b1 = Bank(), Bank()
        N = Network(banks={b0: b0, b1: b1})
        b = N.shock_random()
        self.assertTrue(b == b0 or b == 1)
        print(b.balance_sheet)

