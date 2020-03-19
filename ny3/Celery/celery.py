from celery import Celery

from django.conf import settings
import os

#告诉celery django配置文件位置
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ny3.settings')

app = Celery('ny3')
# 加载配置文件
app.config_from_object('Celery.config')

#celery自动去该参数位置寻找 worker任务
app.autodiscover_tasks(settings.INSTALLED_APPS)
