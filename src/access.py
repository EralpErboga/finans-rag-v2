"""Basic single-process access gate. Deploy directly, not behind an untrusted proxy."""
import hashlib
import hmac
import ipaddress
import json
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from src.accounts import Accounts, AccountError, session_valid

CONFIG = Path(__file__).resolve().parent.parent / '.local/access.json'
_attempts = {}
_lock = threading.Lock()


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()


def allowed(address, networks):
    try:
        ip = ipaddress.ip_address(address)
        if getattr(ip, 'ipv4_mapped', None): ip = ip.ipv4_mapped
        return any(ip in ipaddress.ip_network(n, strict=False) for n in networks)
    except (ValueError, TypeError):
        return False


def authenticate(password, config, address):
    now = time.monotonic()
    with _lock:
        for key in list(_attempts):
            if _attempts[key][1] <= now: del _attempts[key]
        count, expiry = _attempts.get(address, (0, now + 300))
        if count >= 5: return False
        valid = hmac.compare_digest(password_hash(password, config['salt']), config['password_hash'])
        if valid: _attempts.pop(address, None)
        else: _attempts[address] = (count + 1, expiry)
        return valid


def _recovery_screen(st):
    st.title('Kurtarma kodunu kaydet')
    st.success('Hesap işlemi tamamlandı. Yeni şifrenle giriş yapabilirsin.')
    st.write('Bu kod şifreni unuttuğunda hesabını kurtarır. Güvenli bir yerde sakla ve paylaşma. '
             'Önceki kurtarma kodu artık geçersizdir. Bu ekran kapatılınca kod tekrar gösterilmez.')
    st.code(st.session_state['_recovery_code'], language=None)
    if st.button('Kodu kaydettim, giriş yap'):
        st.session_state.clear()
        st.rerun()
    st.stop()


def _show_recovery(st, code):
    st.session_state.clear()
    st.session_state['_recovery_code'] = code
    st.rerun()


def _account_forms(st, accounts, config, address, revision):
    st.title('Finans RAG Giriş')
    st.caption('Kişisel hesabınla giriş yap. İlk kullanımda Yeni kullanıcı oluştur bölümünü aç. '
               'Önceden belirlediğin uygulama parolası, kullanıcı oluşturmak için kayıt anahtarıdır.')
    login, register, reset = st.tabs(['Giriş yap', 'Yeni kullanıcı oluştur', 'Şifremi unuttum'])
    with login:
        with st.form('login'):
            username = st.text_input('Kullanıcı adı', max_chars=32)
            password = st.text_input('Şifre', type='password', max_chars=256)
            submitted = st.form_submit_button('Giriş yap')
        if submitted:
            result = accounts.login(username, password, address)
            if result:
                st.session_state.clear()
                st.session_state.update(_username=result[0], _user_revision=result[1],
                                        _auth_revision=revision, _signed_in=time.time(), _last_seen=time.time())
                st.rerun()
            st.error('Giriş başarısız. Kullanıcı adını ve şifreyi kontrol edin; çok sayıda denemede 5 dakika bekleyin.')
    with register:
        st.write('Hesap oluşturmak için uygulamayı kuran kişiden kayıt anahtarını al. '
                 'Kullanıcıların aynı mali verilere erişimi vardır.')
        with st.form('register'):
            username = st.text_input('Yeni kullanıcı adı', max_chars=32)
            invitation = st.text_input('Kayıt anahtarı (mevcut uygulama parolası)', type='password', max_chars=256)
            password = st.text_input('Yeni şifre', type='password', max_chars=256)
            repeated = st.text_input('Yeni şifre tekrar', type='password', max_chars=256)
            submitted = st.form_submit_button('Kullanıcı oluştur')
        if submitted:
            try:
                code = accounts.create(username, password, repeated, invitation, config, address)
            except AccountError as exc:
                st.error(str(exc))
            else:
                _show_recovery(st, code)
    with reset:
        st.write('Hesap oluştururken verilen kurtarma koduyla yeni şifre belirle. '
                 'Kodu da kaybettiysen uygulamayı kuran kişiye başvur.')
        with st.form('reset'):
            username = st.text_input('Hesabın kullanıcı adı', max_chars=32)
            code = st.text_input('Kurtarma kodu', type='password', max_chars=256)
            password = st.text_input('Belirlenecek yeni şifre', type='password', max_chars=256)
            repeated = st.text_input('Belirlenecek yeni şifre tekrar', type='password', max_chars=256)
            submitted = st.form_submit_button('Şifreyi sıfırla')
        if submitted:
            try:
                new_code = accounts.replace_password(username, code, password, repeated, address, recovery=True)
            except AccountError as exc:
                st.error(str(exc))
            else:
                _show_recovery(st, new_code)
    st.stop()


def _require_access(st):
    try:
        config = json.loads(CONFIG.read_text(encoding='utf-8'))
        assert len(bytes.fromhex(config['salt'])) == 16
        assert len(bytes.fromhex(config['password_hash'])) == 32
        assert config['allowed_networks']
        for network in config['allowed_networks']: ipaddress.ip_network(network, strict=False)
    except (OSError, ValueError, KeyError, TypeError, AssertionError):
        st.error('Erişim yapılandırılmamış. Sunucuda setup_access.py çalıştırılmalı.')
        st.stop()
    address = st.context.ip_address
    # Yerel bağlantıda istemci IP adresi boş gelebilir.
    # Bu durumu yalnızca sunucu loopback adresinde dinliyorsa kabul et.
    # Ağa açık sunucuda boş istemci adresine izin verme.
    if address is None:
        bind_address = st.get_option('server.address')
        try:
            if ipaddress.ip_address(bind_address).is_loopback:
                address = bind_address
        except (ValueError, TypeError):
            pass
    if not allowed(address, config['allowed_networks']):
        st.error('Bu ağ adresinden erişime izin verilmiyor.')
        st.stop()
    revision = hashlib.sha256(json.dumps(config, sort_keys=True).encode()).hexdigest()
    accounts = Accounts(CONFIG.parent / 'users.db')
    if st.session_state.get('_recovery_code'):
        _recovery_screen(st)
    username = st.session_state.get('_username')
    if not session_valid(st.session_state, accounts.revision(username) if username else None, revision):
        if '_username' in st.session_state or '_auth_revision' in st.session_state:
            st.session_state.clear()
        _account_forms(st, accounts, config, address, revision)
    st.session_state['_last_seen'] = time.time()
    st.sidebar.caption(f'Kullanıcı: {username}')
    if st.sidebar.button('Çıkış yap'):
        st.session_state.clear()
        st.rerun()
    with st.sidebar.expander('Şifre değiştir'):
        with st.form('change_password'):
            current = st.text_input('Mevcut şifre', type='password', max_chars=256)
            new = st.text_input('Yeni hesap şifresi', type='password', max_chars=256)
            repeated = st.text_input('Yeni hesap şifresi tekrar', type='password', max_chars=256)
            submitted = st.form_submit_button('Şifreyi değiştir')
        if submitted:
            try:
                code = accounts.replace_password(username, current, new, repeated, address)
            except AccountError as exc:
                st.error(str(exc))
            else:
                _show_recovery(st, code)


def require_access(st):
    try:
        _require_access(st)
    except (sqlite3.Error, OSError):
        st.error('Hesap deposuna erişilemiyor. Disk alanını ve .local klasörünün izinlerini kontrol edin.')
        st.stop()


def setup():
    import getpass
    password = getpass.getpass('Yeni kullanıcı kayıt anahtarı (12–256 karakter): ')
    if not 12 <= len(password) <= 256 or password != getpass.getpass('Tekrar: '):
        raise SystemExit('Parolalar eşleşmiyor veya yeterince uzun değil.')
    networks = input('İzin verilen kurum ağı CIDR (boş=yalnız bu bilgisayar): ').strip()
    permitted = ['127.0.0.1/32', '::1/128']
    if networks:
        for entry in networks.split(','):
            network = ipaddress.ip_network(entry.strip(), strict=False)
            if network.prefixlen == 0: raise SystemExit('Tüm internet ağına izin verilemez.')
            permitted.append(str(network))
    salt = secrets.token_hex(16)
    CONFIG.parent.mkdir(exist_ok=True)
    CONFIG.write_text(json.dumps(dict(salt=salt, password_hash=password_hash(password, salt),
                                     allowed_networks=permitted), indent=2), encoding='utf-8')
    print('Erişim yapılandırıldı. Düz metin parola kaydedilmedi.')
