import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

P=Path(__file__).resolve().parents[1]/'scripts'/'update_data.py'
spec=importlib.util.spec_from_file_location('updater',P)
updater=importlib.util.module_from_spec(spec)
spec.loader.exec_module(updater)


class TestUpdater(unittest.TestCase):
    def test_numbers_with_gallery_and_trainer_prefix(self):
        self.assertEqual(updater.numbers('GG44/GG70'),'GG44/GG70')
        self.assertEqual(updater.numbers('TG11/TG30'),'TG11/TG30')
        self.assertEqual(updater.numbers('SV49/SV94'),'SV49/SV94')
        self.assertEqual(updater.numbers('003/165'),'003/165')

    def test_exact_matching_rejects_wrong_set(self):
        payload=[
            {'product_id':1,'name':'Charizard ex - 199/165','card_number':'199/165','set_name':'Paldea Evolved','market':'30.00'},
            {'product_id':517045,'name':'Charizard ex - 199/165','card_number':'199/165','set_name':'SV: Scarlet & Violet 151','image_url':'https://example.org/card.png','market':'322.37'},
        ]
        with patch.object(updater,'fetch',return_value=payload):
            x=updater.resolve({'name':'Charizard ex','number':'199/165','set':'Scarlet & Violet 151'},None)
        self.assertEqual(x['productId'],517045)
        self.assertTrue(x['verifiedMatch'])

    def test_history_uses_main_holofoil(self):
        x={'Normal':[{'snapshot_date':'2026-10-01','market':2}],
           'Holofoil':[{'snapshot_date':'2026-09-01','market':25.00},{'snapshot_date':'2026-10-01','market':19.0}]}
        series,printing=updater.parse_history(x)
        self.assertEqual(printing,'Holofoil')
        self.assertEqual(series[-1],['2026-10-01',19.0])

    def test_buy_signal_and_wait_signal(self):
        m={'price':22,'change7':-1.1,'change30':-12.1,'drawdown90':-30,'days':90}
        sig,score,reason=updater.recommendation(m,90,3)
        self.assertEqual(sig,'buy')
        self.assertTrue(0<=score<=100)
        m['change7']=-9.2
        sig,_,_=updater.recommendation(m,90,3)
        self.assertEqual(sig,'wait')

    def test_no_buy_without_history(self):
        m={'price':25,'change7':None,'change30':-25,'drawdown90':-30,'days':8}
        self.assertEqual(updater.recommendation(m,99,2)[0],'watch')
        m['price']=101
        self.assertEqual(updater.recommendation(m,99,2)[0],'over')


if __name__=='__main__':unittest.main()
