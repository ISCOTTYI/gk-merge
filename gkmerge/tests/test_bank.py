import unittest
from gkmerge.bank import Bank
from gkmerge.util import add_link

class TestBank(unittest.TestCase):
    def setUp(self):
        self.b = Bank()

    def tearDown(self):
        del self.b

    def test_capital(self):
        self.b.balance_sheet.update(
            assets_ib=20, assets_e=80,
            liabilities_ib=10, liabilities_e=70,
            shock=10, provision=10
        )
        self.assertEqual(self.b.capital(), 0)

    def test_capital_temp_is_None(self):
        self.assertRaises(TypeError, self.b.capital, temp=True)

    def test_capital_temp(self):
        self.b.temp_balance_sheet = dict(self.b.balance_sheet)
        self.b.temp_balance_sheet.update(
            assets_ib=20, assets_e = 80,
            liabilities_ib=10, liabilities_e=70,
            shock=20, provision=10
        )
        self.assertEqual(self.b.capital(temp=True), -10)

    def test_is_solvent(self):
        self.b.balance_sheet.update(
            assets_ib=20, assets_e=80,
            liabilities_ib=10, liabilities_e=70,
            shock=10, provision=10
        )
        self.assertFalse(self.b.is_solvent())

    def test_idiosyncratic_shock(self):
        self.b.balance_sheet["assets_e"] = 10
        self.b.idiosyncratic_shock()
        self.assertEqual(self.b.balance_sheet["shock"], 10)
        self.assertEqual(self.b.balance_sheet["assets_e"], 10)

    def test_update_state_temp_defaulted(self):
        self.b.update_state()
        self.assertTrue(self.b.temp_defaulted)

    def test_update_state_solvent(self):
        self.b.balance_sheet.update(assets_ib=10)
        self.assertIsNone(self.b.temp_defaulted)
 
    def test_update_state_multiple_updates(self):
        pre1, pre2 = Bank(), Bank()
        pre1.balance_sheet.update(liabilities_ib=10)
        pre2.balance_sheet.update(liabilities_ib=10)
        add_link(pre1, self.b, weight=10)
        add_link(pre2, self.b, weight=10)
        self.b.balance_sheet.update(assets_ib=20)

        pre1.update_state()
        pre2.update_state()

        self.assertIsNone(self.b.temp_defaulted)
        self.assertEqual(self.b.temp_balance_sheet["shock"], 20)
        self.assertFalse(self.b.defaulted)

