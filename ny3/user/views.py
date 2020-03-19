import base64
import json
import random
from urllib.parse import urlencode
import requests
from django.conf import settings
from django.db import transaction
from django.shortcuts import render
from django.http import JsonResponse
# Create your views here.
from django.views.generic import View
from .models import *
from dtoken.views import make_token
from django_redis import get_redis_connection
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from .tasks import send_verify
from utils.loging_decorator import login_check
from utils.md5_pwd import hash_pwd
from django.views.decorators.csrf import csrf_exempt,csrf_protect
#用户模块异常码 10100-10199
# 处理和邮箱相关联的redis
email_redis=get_redis_connection('verify_email')
class BaseView(View):
    """
    作为基类，公共调用
    """
    def check_args(self,data,length):
        """
        用来检查用户传递的数据。是否为空。
        params : 前端传递的数据，格式为字典。
        return : 返回检查之后的数据
        """
        if len(data) != length:
            return JsonResponse({'code': 10101, 'error': 'Missing parameters'})
        for key, value in data.items():
            if not value:
                return JsonResponse({'code': 10102, 'error': 'Missing %s parameters' % key})
        return data

class User(BaseView):
    """
    处理用户注册
    """
    @csrf_exempt
    def post(self,request):
        json_obj=json.loads(request.body)
        data=self.check_args(json_obj,4)
        username = data.get('uname')
        email = data.get('email')
        password = data.get('password')
        phone = data.get('phone')
        old_user = UserProfile.objects.filter(username=username)
        if old_user:
            return JsonResponse( {'code': 10103, 'error': 'Your username is already existed'})
        if not phone.isdigit() or len(phone)!=11:
            return JsonResponse({'code': 10104, 'error': 'Your phone is wrong'})
        try:
            validate_email(email)#校验邮箱格式
        except ValidationError as e:
            return JsonResponse({'code': 10105, 'error': 'Your email is wrong'})
        # 哈希加密
        m=hash_pwd(password)
        try:
            UserProfile.objects.create(username=username,password=m.hexdigest(),email=email,phone=phone)
        except Exception as e:
            return JsonResponse({'code': 10105, 'error': 'Server is busy'})
        # 生成激活链接和激活码
        code='{}'.format(random.randint(1000,9999))
        code_str=code+'/'+username
        # 生成激活链接
        active_code=base64.urlsafe_b64encode(code_str.encode()).decode()
        email_redis.set("email_active_%s" % username,active_code,3600)
        verify_url = settings.ACTIVE_HOST + '/dadashop/templates/active.html?code=%s' % (active_code)
        token = make_token(username)
        result = {'code': 200, 'username': username, 'token': token.decode()}
        # 异步发送邮箱验证
        send_verify.delay(email=email, verify_url=verify_url,sendtype=1)
        return JsonResponse(result)

class ActiveView(View):
    """
    邮件激活账号
    GET http://127.0.0.1:8000/v1/user/active?code=xxxxx
    """
    def get(self,request):
        code = request.GET.get('code',None)
        if not code:
            return JsonResponse({'code':10106,'error':'Error activating link parameters'})
        # 反解激活链接
        verify_url = base64.urlsafe_b64decode(code.encode()).decode()

        verify_code,username=verify_url.split('/')
        result = email_redis.get('email_active_%s' % username).decode()

        # 验证前端传来的激活链接和redis中是否一致
        if not result:
            return JsonResponse({'code': 10107, 'error': 'Link is invalid and resend it!'})
        # 判断code中的用户信息和数据库中信息是否一致
        if code != result:
            return JsonResponse({'code': 10108, 'error': 'Link is invalid and resend it!'})
        try:
            user = UserProfile.objects.get(username=username,isActive=False)
        except Exception as e:
            return JsonResponse({'code': 10109, 'error':'User query error'})
        user.isActive = True
        user.save()
        email_redis.delete('email_active_%s'%username)
        return JsonResponse({'code': 200, 'data': 'OK'})

class ModifyPasswordView(BaseView):
    """登录状态下修改密码http://127.0.0.1:8000/v1/user/<username>/password"""
    @login_check
    def post(self,request,username):
        json_str=json.loads(request.body)
        data=self.check_args(json_str,3)
        # {"oldpassword":"","password1":"","password2":""}
        oldpwd=data.get('oldpassword')
        pwd1=data.get('password1')
        pwd2=data.get('password2')
        if oldpwd == pwd1 or oldpwd == pwd2:
            return JsonResponse({'code': 10110, 'error': 'Please Use Different Password!'})
        # 判断两次密码是否一致
        if pwd1 != pwd2:
            return JsonResponse({'code': 10111, 'error': 'Inconsistent passwords!'})
        user=request.user
        # 将旧密码哈希加密与数据库比对
        m=hash_pwd(oldpwd)
        if user.password != m.hexdigest():
            return JsonResponse({'code': 10112, 'error': 'Old password error!'})
        # 将新密码加密替换数据库原密码
        m=hash_pwd(pwd1)
        user.password=m.hexdigest()
        user.save()
        return JsonResponse({'code':200,'data':'ok'})

class SendSmsCodeView(BaseView):
    """给邮箱发送验证码"""
    def post(self,request):
        """
            用户找回密码视图处理函数：
            分为三步：
            1.验证邮箱，并且发送邮件验证码
            2.验证邮件验证码，
            3.验证码验证成功，修改密码
            """
        json_obj = json.loads(request.body)
        data=self.check_args(json_obj,1)
        # a\验证邮箱是否注册
        email = data.get('email')
        try:
            user = UserProfile.objects.get(email=email)
        except Exception as e:
            result={'code':10113,'error':'User query error'}
            return JsonResponse(result)
        # 验证是否发送过验证码
        try:
            email_code = email_redis.get('email_code_%s'%email)
        except Exception as e:
            return JsonResponse({'code': 10114, 'error': 'Verify Code Error'})
        if email_code:
            return JsonResponse({'code':200,'error':'please enter your code!'})
        email_code='{}'.format(random.randint(100000,999999))
        try:
            email_redis.setex('email_code_%s'%email,5*60,email_code)
        except Exception as e:
            return JsonResponse({'code': 10115, 'error': 'Storage authentication code failed'})
        #调度异步任务
        send_verify.delay(email=email, email_code=email_code,sendtype=2)
        return JsonResponse({'code':200,'data':'Ok'})

class VerifyCodeView(BaseView):
    """验证邮件验证码"""
    def post(self,request):
        """
                验证用户邮箱验证码
                :param request:
                :param username: 用户名
                :return:
                """
        json_obj = json.loads(request.body)
        data=self.check_args(json_obj,2)
        email=data.get('email')
        code=data.get('code')
        try:
            email_code = email_redis.get('email_code_%s' % email).decode()
        except Exception as e:
            return JsonResponse({'code': 10116, 'error': 'invalid validation. Resend it.'})

        if  email_code== code:
            return JsonResponse({'code': 200, 'data': '验证码通过！', 'email': email})
        return JsonResponse({'code': 10117, 'error': '验证码错误！'})

class ModifyPwdView(BaseView):
    """
    修改密码
    """
    def post(self,request):
        json_obj = json.loads(request.body)
        data = self.check_args(json_obj, 3)
        #{"password1":"a","password2":"d","email":"282940538@qq.com"}
        email = data.get('email')
        pwd1=data.get('password1')
        pwd2=data.get('password2')
        if pwd1 != pwd2:
            return JsonResponse({'code': 10118, 'error': 'Password Inconsistencies!'})
        try:
            user = UserProfile.objects.get(email=email)
        except Exception as e:
            return JsonResponse({'code': 10119, 'error': 'User query error!'})
        # 读取旧密码
        m=hash_pwd(pwd1)
        user.password = m.hexdigest()
        user.save()
        return JsonResponse({'code': 200, 'data': 'OK'})

class AddressView(BaseView):
    """收货地址变化
    get: 获取用户的绑定的收货地址
    post: 新增用户绑定的收货地址
    delete：实现用户删除地址功能
    put: 实现用户修改地址功能

    """
    @login_check
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    def get(self,request,username):
        user = request.user
        try:
            all_address = Address.objects.filter(uid=user.id, is_alive=True)
            # 获取用户地址，然后用json的地址返回查询后根据querySet 返回相应的字符串。
        except Address.DoesNotExist as e:
            return JsonResponse({'code': 10120, 'error': 'Error in Address Query!'})
        addresslist = []
        for values in all_address:
            each_address = {}
            each_address['id'] = values.id
            each_address['address'] = values.address
            each_address['receiver'] = values.receiver
            each_address['receiver_mobile'] = values.receiver_mobile
            each_address['tag'] = values.tag
            each_address['is_default'] = values.default_address
            addresslist.append(each_address)
        return JsonResponse({'code': 200, 'addresslist': addresslist})

    def post(self,request,username):
        """
        用来提交保存用户的收获地址
        1.先获取相应的用户，然后根据用户的id来绑定地址
        :param request:
        :return:返回保存后的地址以及地址的id
        """
        user=request.user
        json_obj=json.loads(request.body)
        data=self.check_args(json_obj,5)
        receiver = data.get('receiver')
        address = data.get('address')
        receiver_phone = data.get('receiver_phone')
        postcode = data.get('postcode')
        tag = data.get('tag')
        #查看当前用户有其他地址吗？没有的话把地址设为默认地址
        query_address=Address.objects.filter(uid=user)
        default=False
        if not query_address:
            default=True
        try:
            Address.objects.create(
                uid=user,
                receiver=receiver,
                address=address,
                default_address=default,
                receiver_mobile=receiver_phone,
                is_alive=True,
                postcode=postcode,
                tag=tag,
            )
        except Exception as e:
            return JsonResponse({'code': 10121, 'error': 'Address storage exception'})
        return JsonResponse({'code':200,'data':'新增地址成功！'})

    def delete(self,request,id,username):
        """
            删除用户的提交的地址
            :param request: 提交的body中为用户的地址的id
            :param username:
            :return: 删除后用户的所有的收货地址
        """
        # 根据用户发来的地址的id来直接删除用户地址
        try:
            address = Address.objects.get(id=id)
        except Address.DoesNotExist as e:
            # 此刻应该写个日志
            return JsonResponse({'code': 10125, 'error': 'Get address exception'})
        try:
            address.is_alive = False
            address.save()
        except Exception as e:
            return JsonResponse({'code': 10126, 'error': 'delete address error'})
        return JsonResponse({'code': 200, 'data': '删除地址成功！'})
    def put(self,request,username,id):
        """
        根据用户传递过来的收货地址来修改相应的内容
        :param request: 用户请求的对象
        :param address_id:用户地址id
        :return: 返回修改之后的地址的全部内容
        """
        json_obj=json.loads(request.body)
        data=self.check_args(json_obj,5)
        address = data.get('address')
        receiver = data.get('receiver')
        tag = data.get('tag')
        receiver_mobile = data.get('receiver_mobile')
        data_id = data.get('id')
        if int(id) != data_id:
            return JsonResponse({'code':10122,'error':'ID error'})
        try:
            filter_address=Address.objects.get(id=data_id)
        except Exception as e:
            return JsonResponse({'code': 10123, 'error': 'Get address exception!'})
        try:
            filter_address.receiver = receiver
            filter_address.receiver_mobile =receiver_mobile
            filter_address.address = address
            filter_address.tag = tag
            filter_address.save()
        except Exception as e:
            return JsonResponse({'code':10124,'error':'修改地址失败！'})
        return JsonResponse({'code':200, 'data':'修改地址成功！'})

class DefaultAddressView(BaseView):
    """修改默认地址"""
    @login_check
    def post(self,request,username):
        """
        用来修改默认地址
        :param address_id:用户修改地址的id
        """
        # 先根据address_id 来匹配出用户的id
        # 找到用户的id之后选出所有的用户地址。
        # 在将用户地址id为address_id 设为默认
        json_obj = json.loads(request.body)
        data = self.check_args(json_obj, 1)
        address_id = data.get('id')
        # 用户ID
        user = request.user
        user_address = Address.objects.filter(uid=user, is_alive=True)
        for single_address in user_address:
            if single_address.id == address_id:
                single_address.default_address = True
            else:
                single_address.default_address = False
            single_address.save()
        return JsonResponse({'code': 200, 'data': '设为默认成功！'})

class OAuthWeiboUrlView(View):
    def get(self, request):
        """
        用来获取微博第三方登陆的url,返回值为微博登陆页的地址。
        """
        try:
            oauth_weibo_url = get_weibo_login_url()
        except Exception as e:
            print(e)
            return JsonResponse({'code': 10127, 'error': 'Cant get weibo login page'})
        return JsonResponse({'code': 200, 'oauth_url': oauth_weibo_url})
class OAuthWeiboView(BaseView):
    """利用code从微博服务器换取token"""
    def get(self,request):
        code=request.GET.get('code')
#       像微博服务器放松请求，携带code,获取token
        result=get_access_token(code)
        # result:{'access_token': '2.00SZ9FpDMxdPvB04ace4695ayifbSC',
        # 'remind_in': '157679999', 'expires_in': 157679999,
        # 'uid': '3503293092', 'isRealName': 'true'}
        """------------------------------------"""
        """#WeiboUser表中是否有这个 weibo用户数据
        #如果没有数据, 第一次访问 -> 创建WeiboUser数据
        #有的话,1)绑定注册过[uid有值] -> 签发自己token -同普通登陆一样  
        2) 没绑定[uid为空] -> 给前端返回非200的code,触发绑定注册
        """
        # OAuth 2.0 中授权码模式下 如果错误的请求，响应中会字典中会有error键
        if result.get('error'):
            return JsonResponse({'code': 10128, 'error': 'unable get token'})
        wbuid=result.get('uid')
        access_token=result.get('access_token')
        # 在微博表查找是否存在
        try:
            weibo_user=WeiboUser.objects.get(uid=wbuid)
        except Exception as e:
            # 不存在
            weibo_user=WeiboUser.objects.create(uid=wbuid,access_token=access_token)
            # 放回前端创建新的数据
            return JsonResponse({'code': 201, 'uid': wbuid})
        else:
            # 存在,查找userpofile是否关联
            user=weibo_user.username
            if user:
            #     正常签发token
                username=user.username
                token=make_token(username)
                return JsonResponse({'code':200, 'username':username, 'token':token.decode()})
            else:
                return JsonResponse({'code': 201, 'uid': wbuid})
    def post(self,request):
#         前端提交信息，与微博user绑定
        json_obj=json.loads(request.body)
        data=self.check_args(json_obj,5)
        uid = data.get('uid', None)#微博uid
        username = data.get('username', None)
        password = data.get('password', None)
        print(type(password))
        phone = data.get('phone', None)
        email = data.get('email', None)
        # 哈希加密
        m = hash_pwd(password)
        # 创建用户以及微博用户表
        try:
            # 开启事务
            with transaction.atomic():
                user = UserProfile.objects.create(username=username, password=m.hexdigest(),
                                       email=email, phone=phone)
                weibo_user = WeiboUser.objects.get(uid=uid)
                weibo_user.username = user
                weibo_user.save()
        except Exception as e:
            return JsonResponse({'code': 10129, 'error':'create user failed!'})
        # 创建成功返回用户信息
        token = make_token(username)
        result = {'code': 200, 'username': username, 'token': token.decode()}
        return JsonResponse(result)

def get_access_token(code):
    # 向第三方认证服务器发送code 交换token
    token_url = 'https://api.weibo.com/oauth2/access_token'
    # post 请求
    post_data = {
        'client_id': settings.WEIBO_CLIENT_ID,
        'client_secret': settings.WEIBO_CLIENT_SECRET,
        'grant_type': 'authorization_code',
        'redirect_uri': settings.REDIRECT_URI,
        'code': code
    }
    try:
        html = requests.post(token_url, data=post_data)
    except Exception as e:
        print('---weibo exchange error')
        print(e)
        return None
    if html.status_code == 200:
        return json.loads(html.text)
    return None

def get_weibo_login_url():
    params = {'response_code': 'code', 'client_id': settings.WEIBO_CLIENT_ID, 'redirect_uri': settings.REDIRECT_URI}
    login_url = 'https://api.weibo.com/oauth2/authorize?'
    # urlencode方法编码查询字符串
    url = login_url + urlencode(params)
    # url='https://api.weibo.com/oauth2/authorize?response_code=code&...'
    return url

class SmScodeView(BaseView):
    """发送短信验证码"""
    def post(self,request):
        """
        短信测试：
        :param request:
        :return:
        """
        json_obj = json.loads(request.body)
        data = self.check_args(json_obj, 1)
        phone = data.get('phone', None)
        code = "%06d" % random.randint(0, 999999)
        try:
            email_redis.setex("sms_code_%s" % phone, 3 * 60, code)
        except Exception as e:
            return JsonResponse({'code': 10130, 'error': 'Storage authentication code failed'})
        send_verify.delay(phone=phone, code=code, sendtype=0)
        return JsonResponse({'code': 200, 'data': 'OK'})