import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from launch_connector import parse_rows,classify,SheetConnector
from unittest.mock import patch
from subprocess import CompletedProcess
import os,tempfile

class ConnectorTests(unittest.TestCase):
    def test_relative_folder_passes_absolute_script_to_cli(self):
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(os.path.relpath(d))
            with patch('launch_connector.cli_executable',return_value='playwright-cli.cmd'),patch('launch_connector.subprocess.run',return_value=CompletedProcess([],0,'### Result\n{"ok":true}','')) as run:
                self.assertEqual(c.run_script('async () => ({ok:true})'),{'ok':True})
                args=run.call_args.args[0];file=Path(args[args.index('--filename')+1])
                self.assertTrue(file.is_absolute());self.assertEqual(file.parent,Path(run.call_args.kwargs['cwd']))
                self.assertTrue(file.is_file())
    def test_missing_script_not_reported_as_login_failure(self):
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(d)
            with patch('launch_connector.cli_executable',return_value='playwright-cli.cmd'),patch('launch_connector.subprocess.run',return_value=CompletedProcess([],0,'### Error\nENOENT','')):
                with self.assertRaisesRegex(RuntimeError,'脚本文件未找到'):c.call(['run-code'])
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
