import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from src import access
from src.accounts import Accounts, AccountError, digest, session_valid


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = Accounts(self.root/'users.db')
        self.config = {'salt': 'ab'*16, 'password_hash': digest('invitation-for-test', 'ab'*16),
                       'allowed_networks': ['127.0.0.1/32']}
        self.password = 'original-test-password'

    def create(self, name='alice'):
        return self.store.create(name, self.password, self.password, 'invitation-for-test', self.config, 'local')

    def test_registration_authorization_normalization_and_storage(self):
        with self.assertRaises(AccountError):
            self.store.create('alice', self.password, self.password, 'wrong', self.config, 'local')
        self.assertIsNone(self.store.revision('alice'))
        code = self.create('Alice')
        self.assertEqual(self.store.login(' ALICE ', self.password, 'local')[0], 'alice')
        with self.assertRaises(AccountError): self.create('alice')
        raw = (self.root/'users.db').read_bytes()
        for secret in (code, self.password, 'invitation-for-test'):
            self.assertNotIn(secret.encode(), raw)

    def test_password_change_and_recovery_rotation(self):
        recovery = self.create()
        revision = self.store.revision('alice')
        with self.assertRaises(AccountError):
            self.store.replace_password('alice', 'wrong', 'new-test-password', 'new-test-password', 'local')
        self.assertEqual(revision, self.store.revision('alice'))
        next_code = self.store.replace_password('alice', self.password, 'new-test-password', 'new-test-password', 'local')
        self.assertNotEqual(revision, self.store.revision('alice'))
        self.assertIsNone(self.store.login('alice', self.password, 'local'))
        self.assertTrue(self.store.login('alice', 'new-test-password', 'local'))
        with self.assertRaises(AccountError):
            self.store.replace_password('alice', recovery, self.password, self.password, 'local', recovery=True)
        latest = self.store.replace_password('alice', next_code, self.password, self.password, 'local', recovery=True)
        self.assertNotEqual(latest, next_code)
        with self.assertRaises(AccountError):
            self.store.replace_password('alice', next_code, self.password, self.password, 'local', recovery=True)

    def test_throttle_persists_and_expires(self):
        self.create()
        for _ in range(5): self.assertIsNone(self.store.login('alice', 'wrong', 'local'))
        fresh = Accounts(self.root/'users.db')
        self.assertIsNone(fresh.login('alice', self.password, 'other-ip'))
        with patch('src.accounts.time.time', return_value=time.time()+301):
            self.assertTrue(fresh.login('alice', self.password, 'local'))

    def test_reset_is_throttled_and_unknown_user_is_generic(self):
        code = self.create()
        for _ in range(5):
            with self.assertRaises(AccountError):
                self.store.replace_password('alice', 'bad', self.password, self.password, 'local', recovery=True)
        with self.assertRaises(AccountError):
            self.store.replace_password('alice', code, self.password, self.password, 'local', recovery=True)
        with self.assertRaisesRegex(AccountError, 'Doğrulama başarısız'):
            self.store.replace_password('unknown', code, self.password, self.password, 'elsewhere', recovery=True)

    def test_session_expiry_and_revocation(self):
        self.create()
        rev = self.store.revision('alice')
        state = {'_user_revision': rev, '_auth_revision': 'cfg', '_signed_in': 10000, '_last_seen': 10000}
        self.assertTrue(session_valid(state, rev, 'cfg', 10001))
        self.assertFalse(session_valid(state, rev, 'cfg', 11801))
        self.assertFalse(session_valid(state, rev, 'new-cfg', 10001))
        state['_last_seen'] = 40000
        self.assertFalse(session_valid(state, rev, 'cfg', 40001))
        code = self.store.admin_reset('alice', 'admin-reset-password', 'admin-reset-password')
        self.assertFalse(session_valid(state, self.store.revision('alice'), 'cfg', 10001))
        self.assertTrue(code)

    def test_validation_and_account_isolation(self):
        self.create('alice'); self.create('bob')
        bob_revision = self.store.revision('bob')
        for name in ('ab', 'bad name', "x';--"):
            with self.assertRaises(AccountError): self.create(name)
        with self.assertRaises(AccountError):
            self.store.replace_password('alice', self.password, 'short', 'short', 'local')
        self.store.admin_reset('alice', 'admin-reset-password', 'admin-reset-password')
        self.assertEqual(bob_revision, self.store.revision('bob'))

    def test_ui_full_account_lifecycle_and_local_ip(self):
        from streamlit.testing.v1 import AppTest
        config_path = self.root/'access.json'
        config_path.write_text(json.dumps(self.config), encoding='utf-8')
        script = "import streamlit as st\nfrom src.access import require_access\nrequire_access(st)\nst.success('PROTECTED')"
        with patch.object(access, 'CONFIG', config_path), patch('streamlit.context', SimpleNamespace(ip_address=None)), \
                patch('streamlit.get_option', return_value='127.0.0.1'):
            app = AppTest.from_string(script, default_timeout=20).run()
            def enter(label, value):
                next(w for w in app.text_input if w.label == label).input(value)
            def click(label):
                next(w for w in app.button if w.label == label).click().run()
                self.assertFalse(app.exception)
            enter('Yeni kullanıcı adı', 'alice')
            enter('Kayıt anahtarı (mevcut uygulama parolası)', 'invitation-for-test')
            enter('Yeni şifre', self.password); enter('Yeni şifre tekrar', self.password)
            click('Kullanıcı oluştur')
            recovery = app.code[0].value
            click('Kodu kaydettim, giriş yap')
            enter('Kullanıcı adı', 'alice'); enter('Şifre', self.password); click('Giriş yap')
            self.assertTrue(any(w.value == 'PROTECTED' for w in app.success))
            enter('Mevcut şifre', self.password)
            enter('Yeni hesap şifresi', 'changed-test-password')
            enter('Yeni hesap şifresi tekrar', 'changed-test-password')
            click('Şifreyi değiştir')
            replacement = app.code[0].value
            self.assertNotEqual(recovery, replacement)
            click('Kodu kaydettim, giriş yap')
            enter('Hesabın kullanıcı adı', 'alice'); enter('Kurtarma kodu', replacement)
            enter('Belirlenecek yeni şifre', 'reset-test-password')
            enter('Belirlenecek yeni şifre tekrar', 'reset-test-password')
            click('Şifreyi sıfırla'); click('Kodu kaydettim, giriş yap')
            enter('Kullanıcı adı', 'alice'); enter('Şifre', 'reset-test-password'); click('Giriş yap')
            self.assertTrue(any(w.value == 'PROTECTED' for w in app.success))
            click('Çıkış yap')
            self.assertFalse(any(w.value == 'PROTECTED' for w in app.success))
        with patch.object(access, 'CONFIG', config_path), patch('streamlit.context', SimpleNamespace(ip_address=None)), \
                patch('streamlit.get_option', return_value='0.0.0.0'):
            app = AppTest.from_string(script).run()
            self.assertTrue(app.error)
            self.assertEqual(len(app.text_input), 0)


if __name__ == '__main__': unittest.main()
