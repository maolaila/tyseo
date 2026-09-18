import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from launch_connector import parse_rows,classify

class ConnectorTests(unittest.TestCase):
    def test_headers_and_multiline_csv(self):
        text='日期,归属,域名,詞語,Template,Title,Description,Keyword\n2026-09-18,Pony,example.com,体育,r62,title,"two\nlines",词\n'
        rows=parse_rows(text,'launch');self.assertEqual(rows[0]['row'],2);self.assertEqual(rows[0]['cells'][6],'two\nlines')
    def test_stale_clipboard_rejected(self):
        with self.assertRaises(ValueError):parse_rows('归属,域名,上站詞\nPony,example.com,词','launch')
    def test_transition_and_duplicate(self):
        domain=[{'domain':'example.com'}];row={'domain':'example.com','owner':'Pony','row':3,'keyword':'词','cells':['']*17}
        self.assertEqual(classify(domain,{'pending':[row],'launch':[]})[0]['observed'],'waiting_purchase')
        self.assertEqual(classify(domain,{'pending':[],'launch':[row]})[0]['observed'],'purchased_in_launch_sheet')
        self.assertEqual(classify(domain,{'pending':[row],'launch':[row]})[0]['observed'],'needs_attention')
    def test_wrong_owner(self):
        row={'domain':'example.com','owner':'SomeoneElse'}
        self.assertEqual(classify([{'domain':'example.com'}],{'pending':[],'launch':[row]})[0]['observed'],'needs_attention')

if __name__=='__main__':unittest.main()
