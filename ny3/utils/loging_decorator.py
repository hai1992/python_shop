# 检测异常代码10000-10100
from django.http import JsonResponse
import jwt
from django.conf import settings
from user.models import UserProfile
def login_check(func):
    def warpper(self,request,*args,**kwargs):
        token = request.META.get('HTTP_AUTHORIZATION')
        if not token:
            return JsonResponse({'code':10001,'error':'Please login'})
        try:
            payload=jwt.decode(token,settings.TOKEN_KEY,algorithm='HS256')
        except Exception as e:
            return JsonResponse({'code': 10002, 'error': 'Please login'})
        except jwt.ExpiredSignatureError:
            #token过期
            result = {'code':10003, 'error':'Please login'}
            return JsonResponse(result)
        username=payload['username']
        try:
            user = UserProfile.objects.get(username=username)
        except Exception as e:
            result = {'code': 10004, 'error': u'用户名不存在'}
            return JsonResponse(result)
        request.user = user
        return func(self, request,*args, **kwargs)
    return warpper