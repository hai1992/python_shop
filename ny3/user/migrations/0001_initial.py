# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2020-03-07 01:44
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('created_time', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_time', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('username', models.CharField(max_length=11, unique=True, verbose_name='用户名')),
                ('password', models.CharField(max_length=32)),
                ('email', models.CharField(max_length=50, verbose_name='邮箱')),
                ('phone', models.CharField(max_length=11, verbose_name='手机')),
                ('isActive', models.BooleanField(default=False, verbose_name='激活状态')),
            ],
            options={
                'db_table': 'user_profile',
            },
        ),
    ]
