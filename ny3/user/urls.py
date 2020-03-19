from django.conf.urls import url
from . import views
urlpatterns=[
    url(r'^$',views.User.as_view()),
    url(r'^/activation$',views.ActiveView.as_view()),
    # 用户登陆状态下修改密码
    url(r'^/(?P<username>[\w]{1,20})/password$', views.ModifyPasswordView.as_view()),
    #用户忘记密码
    # 给邮箱发送验证码
    url(r'^/password/sms$',views.SendSmsCodeView.as_view()),
    # 提交验证码
    url(r'^/password/verification$',views.VerifyCodeView.as_view()),
    # 修改密码
    url(r'^/password/new$',views.ModifyPwdView.as_view()),
    #收货地址变化
    url(r'^/(?P<username>[\w]{1,20})/address$', views.AddressView.as_view()),
    #改删
    url(r'^/(?P<username>[\w]{1,20})/address/(?P<id>[\d]{1,5})$', views.AddressView.as_view()),
    # 设置默认地址
    url(r'^/(?P<username>[\w]{1,20})/address/default$', views.DefaultAddressView.as_view()),
    ## 用于重定向微博授权页面
    url(r'^/weibo/authorization$',views.OAuthWeiboUrlView.as_view()),
    # 携带code访问django
    url(r'^/weibo/users',views.OAuthWeiboView.as_view()),
    # 发送短信验证码
    url(r'^/sms/code',views.SmScodeView.as_view()),


]