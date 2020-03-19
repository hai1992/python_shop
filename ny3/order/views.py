import datetime
import json
import os

from alipay import AliPay
from django.db import transaction
from django.shortcuts import render

# Create your views here.
from django.views.generic.base import View

from utils.loging_decorator import login_check
from django.http import JsonResponse, HttpResponse
from user.models import Address
from django_redis import get_redis_connection
from goods.models import SKU, SaleAttrValue, SPUSaleAttr
from django.conf import settings
from .models import *
cart_redis = get_redis_connection('carts')
private_key = open(os.path.join(settings.BASE_DIR,"Alipay/key_file/app_private_key.pem")).read()
ali_public_key = open(os.path.join(settings.BASE_DIR,"Alipay/key_file/alipay_publick_key.pem")).read()
class OrderProcessingnView(View):
    @login_check
    def get(self,request):
        """
        处理业务确认订单和展示订单
        状态码0 -- 处理确认订单详情业务
        状态码1 -- 处理展示订单详情业务
        状态码2 -- 处理确认收货业务
        :param request:
        :return:
        """
        try:
            # 处理订单状态码
            status = int(request.GET.get('status'))
            # 商品结算码
            settlement = int(request.GET.get('settlement_type'))
        except Exception as e:
            print(e)
            return JsonResponse({'code':20000})
        user=request.user
        #确认订单业务
        if status==0:
            # 获取收货地址
            address_list=self.get_address(user)
            # 2.组织商品数据
            if settlement==0:
                #购物车结算,获取购物车数据
                cart_dict=self.get_cart_data(user)
                if not cart_dict:
                    return JsonResponse({'code':20033})
                skus = SKU.objects.filter(id__in=cart_dict.keys())
                # 3.获取商品列表，总数量,总价格,运费,实付款(总价格+运费)
                sku_list, total_count, total_amount, transit, payment_amount = self.get_order_list(skus,cart_dict)
            elif settlement == 1:
                sku_id = request.GET.get('sku_id')
                count = request.GET.get('buy_num')
                skus = SKU.objects.filter(id=sku_id)
                cart_dict = None
                # 获取商品列表，总数量,总价格,运费,实付款(总价格+运费)
                sku_list, total_count, total_amount, transit, payment_amount = self.get_order_list(skus,cart_dict,count)
            # 3.组织数据
            data = {
                'addresses': address_list,
                'sku_list': sku_list,
                'total_count': total_count,
                'total_amount': total_amount,
                'transit': transit,
                'payment_amount': payment_amount
            }
            return JsonResponse({'code':200, 'data':data, 'base_url':settings.PIC_URL})
        elif status==1:
            # print(os.path.join(os.getcwd(), "utils/key_file/alipay_public_key.pem"))
            # print(os.path.join(BASE_DIR, "utils/key_file/alipay_public_key.pem"))
            # 获取状态码为依据返回指定状态的订单.
            order_status = request.GET.get("order_status")
            if order_status=='0':
                order_list = OrderInfo.objects.filter(user=user)
            else:
                order_list = OrderInfo.objects.filter(user=user, status=order_status)
            order_lists=[]
            for order in order_list:
                goods_sku=OrderGoods.objects.filter(order=order)
                skus=[]
                for good in goods_sku:
                    sku=good.sku
                    sku_sale_attr_names, sku_sale_attr_vals, _ = self.get_sku_list(sku)
                    skus.append({
                        'id': sku.id,
                        'default_image_url': str(sku.default_image_url),
                        'name': sku.name,
                        'price': sku.price,
                        'count': good.count,
                        'total_amount': sku.price * good.count,
                        "sku_sale_attr_names": sku_sale_attr_names,
                        "sku_sale_attr_vals": sku_sale_attr_vals,
                    })
                    # 2.组织订单信息
                order_lists.append({
                    "order_id": order.order_id,
                    "order_total_count": order.total_count,
                    "order_total_amount": order.total_amount,
                    "order_freight": order.freight,
                    "address": {
                        "title": order.address.tag,
                        "address": order.address.address,
                        "mobile": order.address.receiver_mobile,
                        "receiver": order.address.receiver
                    },
                    "status": order.status,
                    "order_sku": skus,
                    "order_time": str(order.created_time)[0:19]
                    })
            data = {
                'orders_list': order_lists,
            }
            return JsonResponse({"code": 200,"data": data, 'base_url':settings.PIC_URL})
        # 买家确认收货业务
        elif status==2:
            order_id = request.GET.get("order_id")
            order = OrderInfo.objects.filter(order_id=order_id)[0]
            order.status = 4
            order.save()
            return JsonResponse({"code": 200, 'base_url': settings.PIC_URL})

    # 获取商品列表，总数量, 总价格, 运费, 实付款
    def get_order_list(self,skus,cart_dict=None,count=None):
        """
        :param skus:
        :param cart_dict:
        :return: sku_list(sku列表)
        :return: total_count(总数量)
        :return: total_amount(总价格)
        :return: payment_amount(实付款)
        """
        sku_list = []
        total_count = 0
        total_amount = 0
        for sku in skus:
            # 获取sku的销售属性、销售属性值和购买数量.
            sku_sale_attr_names, sku_sale_attr_vals, count = self.get_sku_list(sku, cart_dict, count)
            # sku商品入列表准备数据
            sku_list.append({
                'id': sku.id,
                'default_image_url': str(sku.default_image_url),
                'name': sku.name,
                'price': sku.price,
                'count': count,
                'total_amount': sku.price * int(count),
                "sku_sale_attr_names": sku_sale_attr_names,
                "sku_sale_attr_vals": sku_sale_attr_vals,
            })
            # 计算总数量
            total_count += int(count)
            # 计算总金额
            total_amount += sku.price * int(count)
            # 3.运费
        transit = 10
        # 4.实付款(总金额+运费)
        payment_amount = total_amount + transit
        return sku_list, total_count, total_amount, transit, payment_amount

    # 获取单个sku的信息
    def get_sku_list(self,sku, cart_dict=None, s_count=None):
        if cart_dict:
            s_count = int(cart_dict[sku.id]['count'])
        sku_sale_attr_names = []
        sku_sale_attr_val = []
        saleattr_vals = SaleAttrValue.objects.filter(sku_id=sku.id)
        for val in saleattr_vals:
            sku_sale_attr_val.append(val.sale_attr_value_name)
            sku_sale_attr_name=SPUSaleAttr.objects.filter(id=val.sale_attr_id_id)[0]
            sku_sale_attr_names.append(sku_sale_attr_name.sale_attr_name)
        return sku_sale_attr_names, sku_sale_attr_val, s_count

    #获取购物车数据
    def get_cart_data(self,user):
        carts=cart_redis.hgetall('cart_%d'%user.id)
        cart_dict={}
        for sku_id, status in carts.items():
            if json.loads(status)['selected']==1:
                cart_dict[int(sku_id.decode())] = json.loads(status)
        return cart_dict

    # 获取收货地址
    def get_address(self,user):
        addresss=Address.objects.filter(is_alive=True,uid=user)
        # addresss=user.address.filter(is_alive=True)
        address_list=[]
        for addr in addresss:
            if addr.default_address == False:
                address_list.append({
                    "id": addr.id,
                    "name": addr.receiver,
                    "mobile": addr.receiver_mobile,
                    "title": addr.tag,
                    "address": addr.address
                })
            else:
                address_list.insert(0, {
                    "id": addr.id,
                    "name": addr.receiver,
                    "mobile": addr.receiver_mobile,
                    "title": addr.tag,
                    "address": addr.address
                })
        return address_list
    @login_check
    def post(self,request):
        """
        处理业务生成订单,跳转订单支付,响应支付成功
        状态码0 -- 生成订单
        状态码1 -- 跳转订单支付
        状态码2 -- 跳转立即购买
        :param request:
        :return:
        """
        status = json.loads(request.body).get("status")
        user=request.user
        if status==0:
            # 生成订单
            address_id=json.loads(request.body).get("address_id")
            settlement_type = json.loads(request.body).get("settlement_type")
            try:
                address=Address.objects.get(id=address_id)
            except Exception as e:
                return JsonResponse({'code': 50102, 'errmsg': '收货地址无效'})
            now = datetime.datetime.now()
            with transaction.atomic():
                # 开启事务
                sid=transaction.savepoint()
                #创建订单id
                order_id='{}{}'.format(now.strftime('%Y%m%d%H%M%S'),user.id)
                total_count=0
                total_amount=0
                order = OrderInfo.objects.create(order_id=order_id,
                                                 user=user,address=address,
                                                 total_amount=total_amount,
                                                 total_count=total_count,
                                                 freight=1,status=1,
                                                 pay_method=1)
                #修改数据库中相应的数据
                cart_dict=self.get_cart_data(user)
                skus=SKU.objects.filter(id__in=cart_dict.keys())
                # 用以存储购物车中选中的商品,用作订单生成后删除redis中的商品.
                sku_ids = []
                for sku in skus:
                    cart_count=cart_dict[sku.id].get('count')
                    sku_ids.append(sku.id)
                    if cart_count>sku.stock:
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 50103, 'errmsg': '商品[%d]库存不足' % sku.id})
                    # 更新数据库,result表示sql语句修改数据的个数
                    result = SKU.objects.filter(id=sku.id).update(stock=sku.stock - cart_count,
                                                                sales=sku.sales + cart_count)
                    if result==0:
                        # 库存发生变化，未成功购买,回滚数据库
                        transaction.savepoint_rollback(sid)
                        return JsonResponse({'code': 50103, 'errmsg': '商品[%d]库存不足' % sku.id})
                   #创建订单商品对象
                    _=OrderGoods.objects.create(order_id=order_id,sku=sku,
                                                         count=cart_count,price=sku.price)
                    #计算总金额，总数量
                    total_count +=cart_count
                    total_amount += sku.price*cart_count
                #修改订单中的金额和数量
                order.total_amount += total_amount
                order.total_count += total_count
                order.freight=10
                order.save()
                #提交事务
                transaction.savepoint_commit(sid)
            #从redis中删除已经购买的商品
            for sku_id in sku_ids:
                cart_redis.hdel('cart_%d' % user.id, sku_id)
            #生成支付宝链接
            sku_goods = OrderGoods.objects.filter(order=order_id)
            # 生成alipay查询字符串
            order_string = self.get_order_string(order.order_id, order.total_amount + 10, sku_goods)
            pay_url="https://openapi.alipaydev.com/gateway.do?" + order_string
            # 5.组织数据
            data = {
                'saller': '达达商城',
                'total_amount': order.total_amount + order.freight,
                'order_id': order_id,
                'pay_url': pay_url
            }
            # 响应
            return JsonResponse({'code': 200, 'data': data})
        elif status==1:
            order_id = json.loads(request.body).get("order_id")
            order = OrderInfo.objects.filter(order_id=order_id)[0]
            # 1.生成支付链接
            sku_goods = OrderGoods.objects.filter(order=order_id)
            order_string = self.get_order_string(order.order_id, order.total_amount, sku_goods)
            # 构建让用户跳转的支付链接
            pay_url = "https://openapi.alipaydev.com/gateway.do?" + order_string
            # 2.组织数据
            data = {
                'saller': '达达商城',
                'total_amount': order.total_amount + 10,
                'order_id': order_id,
                'pay_url': pay_url
            }
            # 响应
            return JsonResponse({'code': 200, 'data': data})




    def get_order_string(self,order_id,total_amount,sku_goods):
        """
        :param order_id:
        :param total_amount:
        :return: order_string
        """
        trade_name = []
        for sku_good in sku_goods:
            trade_name.append(sku_good.sku.name + "(" + sku_good.sku.caption + ")")
        alipay = AliPay(
            appid="2016101900725372",
            app_notify_url=None,  # 默认回调url-　阿里与商户后台交互
            # 使用的文件读取方式,载入支付秘钥
            app_private_key_string=private_key,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            # 使用文件读取的方式,载入支付报公钥
            alipay_public_key_string=ali_public_key,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True  # 默认False
        )
        # 电脑网站支付，需要跳转到https://openapi.alipaydev.com/gateway.do? + order_string
        # 测试方式此为支付宝沙箱环境
        order_string = alipay.api_alipay_trade_page_pay(
            out_trade_no=order_id,
            total_amount=int(total_amount),
            subject=("\n".join(trade_name)),
            # 回转url,　支付宝与买家业务处理完毕(支付成功)将玩家重定向到此路由,带着交易的参数返回
            # return_url="http://" + IP_URL + ":8000/v1/orders/success/",
            return_url = "http://127.0.0.1:7000/dadashop/templates/pay_success.html",
            notify_url="http://127.0.0.1:8000/v1/orders/result/"  # 可选, 不填则使用默认notify url
        )
        return order_string
class AlipayResultView(View):
    # 获取参数字典和验签结果
    def get_sdict_ali_verify(self, request, method):
        """
        :param request:
        :param method: 请求方式
        :return: success_dict,ali_verufy,alipay
        """
        success_dict = {}
        if method == 1:
            for key, val in request.GET.items():
                success_dict[key] = val
        if method == 2:
            for key, val in request.POST.items():
                success_dict[key] = val
        # 1.剔除掉sign做验签准备
        sign = success_dict.pop("sign", None)
        # 2.生成alipay对象
        alipay = AliPay(
            appid="2016101900725372",
            app_notify_url=None,  # 默认回调url-　阿里与商户后台交互
            # 使用的文件读取方式,载入支付秘钥
            app_private_key_string=private_key,
            # 支付宝的公钥，验证支付宝回传消息使用，不是你自己的公钥,
            # 使用文件读取的方式,载入支付报公钥
            alipay_public_key_string=ali_public_key,
            sign_type="RSA2",  # RSA 或者 RSA2
            debug=True
        )
        # 3.使用支付宝接口进行验签
        ali_verify = alipay.verify(success_dict, sign)
        return success_dict, ali_verify, alipay

    # 重定向接口
    def get(self,request):
        """支付宝付款完成后重定向return_url"""
        # 1.获取参数字典,验签结果,alipay对象
        success_dict, ali_verify, alipay = self.get_sdict_ali_verify(request, 1)
        if ali_verify:
            order_id = success_dict.get('out_trade_no',None)
            order = OrderInfo.objects.filter(order_id=order_id)[0]
            total_amount = success_dict.get('total_amount', None)
            if order.status==2:
                data = {
                    "order_id": order_id,
                    "total_amount": total_amount
                }
                return JsonResponse({"code": 200, "data": data})
            else:
                #主动询问交易是否成功
                result = alipay.api_alipay_trade_query(out_trade_no=order_id)
                if result.get("trade_status", "") == "TRADE_SUCCESS":
                    order.status=2
                    order.save()
                    data = {
                        "order_id": order_id,
                        "total_amount": total_amount
                    }
                    return JsonResponse({"code": 200, "data": data})
                else:
                    data = {
                        "order_id": order_id,
                        "total_amount": total_amount
                    }
                    return JsonResponse({"code": 50105, "data": data})
        else:
            return HttpResponse("非法访问")

    # 回调接口
    def post(self,request):
        # 1.获取参数字典,验签结果,alipay对象
        success_dict, ali_verify, alipay = self.get_sdict_ali_verify(request, 2)
        # 2.根据验证结果进行业务处理
        print(3)
        if ali_verify:
            trade_status = success_dict.get('trade_status', None)
            if trade_status == "TRADE_SUCCESS":
                order_id = success_dict.get('out_trade_no', None)
                order = OrderInfo.objects.filter(order_id=order_id)[0]
                order.status = 2
                order.save()
                return HttpResponse("seccess")
        else:
            return HttpResponse("非法访问")