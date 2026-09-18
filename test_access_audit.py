import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src import access, audit


class AccessAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.config={'salt':'ab'*16,'password_hash':access.password_hash('test-only-password', 'ab'*16),
                     'allowed_networks':['127.0.0.1/32','10.30.0.0/24']}
        access._attempts.clear()

    def test_network_boundary(self):
        for address in ['127.0.0.1','10.30.0.42']:
            self.assertTrue(access.allowed(address,self.config['allowed_networks']))
        for address in ['10.31.0.1','8.8.8.8',None,'bad']:
            self.assertFalse(access.allowed(address,self.config['allowed_networks']))

    def test_password_and_throttling(self):
        self.assertTrue(access.authenticate('test-only-password',self.config,'local'))
        for _ in range(5): self.assertFalse(access.authenticate('wrong',self.config,'local'))
        self.assertFalse(access.authenticate('test-only-password',self.config,'local'))

    def test_ui_gate_and_login_logout(self):
        from streamlit.testing.v1 import AppTest
        path=self.root/'access.json';path.write_text(json.dumps(self.config))
        access.Accounts(self.root/'users.db').create('test_user', 'test-only-password', 'test-only-password',
                                                    'test-only-password', self.config, 'local')
        with patch.object(access,'CONFIG',path), patch('streamlit.context',SimpleNamespace(ip_address='127.0.0.1')):
            app=AppTest.from_file('app.py',default_timeout=20).run()
            self.assertFalse(app.exception);self.assertEqual(len(app.chat_input),0)
            app.text_input[0].input('test_user');app.text_input[1].input('wrong');app.button[0].click().run()
            self.assertEqual(len(app.chat_input),0)
            app.text_input[1].input('test-only-password');app.button[0].click().run()
            self.assertFalse(app.exception);self.assertEqual(len(app.chat_input),1)
            next(b for b in app.button if b.label=='Çıkış yap').click().run()
            self.assertEqual(len(app.chat_input),0)

    def test_ui_missing_config_denies_access(self):
        from streamlit.testing.v1 import AppTest
        with patch.object(access,'CONFIG',self.root/'missing.json'):
            app=AppTest.from_file('app.py',default_timeout=20).run()
            self.assertEqual(len(app.chat_input),0);self.assertTrue(app.error)

    def test_ui_disallowed_ip(self):
        from streamlit.testing.v1 import AppTest
        path=self.root/'access.json';path.write_text(json.dumps(self.config))
        with patch.object(access,'CONFIG',path),patch('streamlit.context',SimpleNamespace(ip_address='10.31.0.1')):
            app=AppTest.from_file('app.py',default_timeout=20).run()
            self.assertEqual(len(app.text_input),0);self.assertEqual(len(app.chat_input),0)

    def test_audit_redaction_error_and_rotation(self):
        with patch.object(audit,'LOG_DIR',self.root),patch.object(audit,'_logger',None):
            try:
                audit.record('parola=secret-value',{'type':'ERROR','answer':'token=hidden-value','sources':[]},1.2,'test')
                handler=audit._logger.handlers[0];handler.maxBytes=600;handler.backupCount=2
                for _ in range(10): audit.record('normal',{'type':'FINANCE','answer':'100 TL','sources':[{'source':'Mizan','section':'Hesap'}]},.2,'test')
                self.assertLessEqual(len(list(self.root.glob('queries.jsonl*'))),3)
                row=json.loads((self.root/'queries.jsonl').read_text(encoding='utf-8').splitlines()[-1])
                self.assertEqual(row['channel'],'FINANCE');self.assertFalse(row['error'])
                self.assertIn('request_id',row);self.assertEqual(row['seconds'],.2)
                self.assertNotIn('secret-value',audit.scrub('parola=secret-value'))
                self.assertNotIn('hidden-value',audit.scrub('token=hidden-value'))
            finally:
                if audit._logger:
                    for h in audit._logger.handlers:h.close()


if __name__=='__main__': unittest.main()
