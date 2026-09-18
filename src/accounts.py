"""Local personal accounts. Passwords/recovery codes are never stored in plaintext."""
import hashlib
import hmac
import re
import secrets
import sqlite3
import time
from contextlib import contextmanager


class AccountError(ValueError):
    pass


def digest(value, salt):
    return hashlib.pbkdf2_hmac('sha256', value.encode(), bytes.fromhex(salt), 600000).hex()


def username_key(value):
    return value.strip().lower()


def check_password(password, repeated):
    if not 12 <= len(password) <= 256:
        raise AccountError('Şifre 12–256 karakter olmalı.')
    if password != repeated:
        raise AccountError('Şifreler eşleşmiyor.')


class Accounts:
    def __init__(self, path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    username TEXT PRIMARY KEY,
                    salt TEXT NOT NULL, password_hash TEXT NOT NULL,
                    recovery_salt TEXT NOT NULL, recovery_hash TEXT NOT NULL,
                    revision TEXT NOT NULL, created_at REAL NOT NULL);
                CREATE TABLE IF NOT EXISTS attempts (
                    bucket TEXT PRIMARY KEY, failures INTEGER NOT NULL, expires REAL NOT NULL);
            ''')

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def _credential(self, value):
        salt = secrets.token_hex(16)
        return salt, digest(value, salt)

    def _matches(self, value, salt, expected):
        if len(value) > 256:
            return False
        return hmac.compare_digest(digest(value, salt), expected)

    def _attempt(self, db, action, address, username, verify):
        """Serialize verification and persist failures, including across restarts."""
        now = time.time()
        db.execute('DELETE FROM attempts WHERE expires <= ?', (now,))
        buckets = [f'{action}:ip:{address}']
        if username:
            buckets.append(f'{action}:user:{username}')
        for bucket in buckets:
            row = db.execute('SELECT failures FROM attempts WHERE bucket=?', (bucket,)).fetchone()
            if row and row['failures'] >= 5:
                return False
        valid = verify()
        for bucket in buckets:
            if valid:
                db.execute('DELETE FROM attempts WHERE bucket=?', (bucket,))
            else:
                db.execute('''INSERT INTO attempts VALUES (?, 1, ?)
                    ON CONFLICT(bucket) DO UPDATE SET failures=failures+1''', (bucket, now+300))
        return valid

    def create(self, username, password, repeated, invitation, config, address):
        username = username_key(username)
        check_password(password, repeated)
        if not re.fullmatch(r'[a-z0-9_]{3,32}', username):
            raise AccountError('Kullanıcı adı 3–32 karakter olmalı; a-z, 0-9 ve alt çizgi kullanın.')
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            valid = self._attempt(db, 'register', address, '', lambda:
                self._matches(invitation, config['salt'], config['password_hash']))
            if valid:
                exists = db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone()
                if not exists:
                    recovery = secrets.token_urlsafe(24)
                    salt, hashed = self._credential(password)
                    rsalt, rhash = self._credential(recovery)
                    db.execute('INSERT INTO users VALUES (?,?,?,?,?,?,?)',
                               (username, salt, hashed, rsalt, rhash, secrets.token_hex(16), time.time()))
        # Hatalı denemeyi kaydettikten sonra hata döndür.
        if not valid:
            raise AccountError('Kayıt yetkilendirmesi başarısız. Bilgiyi kontrol edin; çok sayıda denemede 5 dakika bekleyin.')
        if exists:
            raise AccountError('Bu kullanıcı adı kullanılıyor. Farklı bir ad seçin.')
        return recovery

    def login(self, username, password, address):
        username = username_key(username)[:256]
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            # Kayıtsız kullanıcı için de aynı özetleme işlemini uygula.
            salt, expected = (row['salt'], row['password_hash']) if row else ('00'*16, '00'*32)
            valid = self._attempt(db, 'login', address, username,
                                  lambda: self._matches(password, salt, expected) and row is not None)
        return (username, row['revision']) if valid else None

    def revision(self, username):
        with self.connection() as db:
            row = db.execute('SELECT revision FROM users WHERE username=?', (username,)).fetchone()
        return row['revision'] if row else None

    def replace_password(self, username, proof, password, repeated, address, *, recovery=False):
        username = username_key(username)[:256]
        check_password(password, repeated)
        action = 'reset' if recovery else 'change'
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT * FROM users WHERE username=?', (username,)).fetchone()
            field = 'recovery_' if recovery else ''
            salt = row[field+'salt'] if row else '00'*16
            expected = row['recovery_hash' if recovery else 'password_hash'] if row else '00'*32
            valid = self._attempt(db, action, address, username,
                                  lambda: self._matches(proof.strip() if recovery else proof, salt, expected) and row is not None)
            if valid:
                code = self._replace(db, username, password)
        if not valid:
            raise AccountError('Doğrulama başarısız. Bilgileri kontrol edin; çok sayıda denemede 5 dakika bekleyin.')
        return code

    def _replace(self, db, username, password):
        code = secrets.token_urlsafe(24)
        salt, hashed = self._credential(password)
        rsalt, rhash = self._credential(code)
        db.execute('''UPDATE users SET salt=?, password_hash=?, recovery_salt=?,
                   recovery_hash=?, revision=? WHERE username=?''',
                   (salt, hashed, rsalt, rhash, secrets.token_hex(16), username))
        return code

    def admin_reset(self, username, password, repeated):
        """Local terminal/OS administrator recovery, never exposed in the web UI."""
        username = username_key(username)
        check_password(password, repeated)
        with self.connection() as db:
            db.execute('BEGIN IMMEDIATE')
            if not db.execute('SELECT 1 FROM users WHERE username=?', (username,)).fetchone():
                raise AccountError('Kullanıcı bulunamadı.')
            code = self._replace(db, username, password)
            for action in ('login', 'reset', 'change'):
                db.execute('DELETE FROM attempts WHERE bucket=?', (f'{action}:user:{username}',))
        return code


def session_valid(state, revision, config_revision, now=None):
    now = time.time() if now is None else now
    return bool(revision and state.get('_user_revision') == revision
                and state.get('_auth_revision') == config_revision
                and 0 <= now-state.get('_signed_in', 0) < 8*3600
                and 0 <= now-state.get('_last_seen', 0) < 30*60)
