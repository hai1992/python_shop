from django.conf.urls import url
from . import views

urlpatterns=[
    url(r'^/processing/$', views.OrderProcessingnView.as_view()),
    url(r'^/result/$',views.AlipayResultView.as_view())

]