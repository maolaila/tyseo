import sys
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from z_link_audit import local_path, link_head


class LinkClassificationTests(unittest.TestCase):
    def test_local_relative_and_query_targets(self):
        base='http://127.0.0.1:6316'
        self.assertEqual(local_path(base,'/zuqiu/news/','/zuqiu'),('/zuqiu','local'))
        self.assertEqual(local_path(base,'/zuqiu/news/','next?q=英超'),('/zuqiu/news/next?q=英超','local'))

    def test_non_navigation_is_not_a_passed_link(self):
        base='http://127.0.0.1:6316'
        for href,kind in ((None,'no_href'),('#','placeholder_fragment'),('javascript:void(0)','non_http'),('https://other.example/a','external')):
            self.assertEqual(local_path(base,'/',href)[1],kind)

    def test_real_status_and_redirect_to_missing_are_detected(self):
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                status=302 if self.path=='/redirect' else 404
                self.send_response(status)
                if status==302:self.send_header('Location','/missing')
                self.end_headers()
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            self.assertEqual(link_head(base,'/missing')['status'],404)
            self.assertEqual(link_head(base,'/redirect')['destination_status'],404)
        finally:
            server.shutdown();server.server_close();thread.join(timeout=2)


if __name__=='__main__':unittest.main()
