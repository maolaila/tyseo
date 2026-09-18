import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from launch_connector import parse_rows,SheetConnector
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
    def test_temporary_login_script_and_cli_log_do_not_keep_password(self):
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(d);secret='fixture-password'
            output='### Result\n{"ok":true}\n### Ran code '+secret
            with patch('launch_connector.cli_executable',return_value='playwright-cli.cmd'),patch('launch_connector.subprocess.run',return_value=CompletedProcess([],0,output,'')):
                c.run_script('async()=>'+repr(secret),redact=(secret,))
            self.assertNotIn(secret,(Path(d)/'read-sheet.js').read_text())
            self.assertNotIn(secret,(Path(d)/'latest-cli.log').read_text())
    def test_missing_script_not_reported_as_login_failure(self):
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(d)
            with patch('launch_connector.cli_executable',return_value='playwright-cli.cmd'),patch('launch_connector.subprocess.run',return_value=CompletedProcess([],0,'### Error\nENOENT','')):
                with self.assertRaisesRegex(RuntimeError,'脚本文件未找到'):c.call(['run-code'])
    def test_headers_and_multiline_csv(self):
        text='日期,归属,域名,詞語,Template,Title,Description,Keyword\n2026-09-18,Pony,example.com,体育,r62,title,"two\nlines",词\n'
        rows=parse_rows(text,'launch');self.assertEqual(rows[0]['row'],2);self.assertEqual(rows[0]['cells'][6],'two\nlines')
    def test_rate_limit_is_not_login_failure(self):
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(d)
            with patch.object(c,'run_script',return_value={'ok':False,'http_status':429}):
                with self.assertRaisesRegex(RuntimeError,'HTTP 429'):c.read()
    def test_writer_limits_ranges_and_verifies_readback(self):
        from unittest.mock import Mock
        import copy
        before={'pending':[],'launch':[]};updates=[]
        for rownum,name in [(3539,'one.example.com'),(3541,'two.example.com')]:
            cells=['']*17;cells[1]='Pony';cells[2]=name
            before['launch'].append({'row':rownum,'owner':'Pony','domain':name,'cells':cells})
            updates.append({'row':rownum,'domain':name,'before':['']*4,'before_cells':cells[:16],'values':['r62','Title','Description','Keywords']})
        after=copy.deepcopy(before)
        for row,u in zip(after['launch'],updates):row['cells'][4:8]=u['values']
        with tempfile.TemporaryDirectory() as d:
            c=SheetConnector(d);c.read=Mock(return_value=after);c.run_script=Mock(return_value={'pasted':True})
            self.assertEqual(c.write_tdk(updates,fresh=before),after)
            script=c.run_script.call_args.args[0]
            self.assertIn('E3539:H3539',script);self.assertIn('E3541:H3541',script)
            self.assertNotIn('Q3539',script);self.assertNotIn('E3539:H3541',script)
            changed=copy.deepcopy(before);changed['launch'][0]['owner']='Other';c.run_script.reset_mock()
            with self.assertRaises(ValueError):c.write_tdk(updates,fresh=changed)
            c.run_script.assert_not_called()
    def test_stale_clipboard_rejected(self):
        with self.assertRaises(ValueError):parse_rows('归属,域名,上站詞\nPony,example.com,词','launch')
if __name__=='__main__':unittest.main()
