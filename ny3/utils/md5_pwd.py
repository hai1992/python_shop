from hashlib import md5
from django.conf import settings
def hash_pwd(password):
    m=md5()
    m.update(password.encode())
    m.update(settings.PASSWORD_SOLT.encode())
    return m