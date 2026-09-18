"""Only the local machine administrator should run this recovery command."""
import getpass
from src.access import CONFIG
from src.accounts import Accounts, AccountError


if __name__ == '__main__':
    path = CONFIG.parent / 'users.db'
    if not path.exists():
        raise SystemExit('Henüz kullanıcı hesabı oluşturulmamış.')
    username = input('Şifresi sıfırlanacak kullanıcı adı: ')
    password = getpass.getpass('Yeni şifre (12–256 karakter): ')
    repeated = getpass.getpass('Tekrar: ')
    try:
        code = Accounts(path).admin_reset(username, password, repeated)
    except AccountError as exc:
        raise SystemExit(str(exc))
    print('Şifre sıfırlandı; önceki oturumlar ve kurtarma kodu geçersizleşti.')
    print('Yeni kurtarma kodunu kullanıcıya güvenli biçimde iletin: ' + code)
