from django.shortcuts import render
from django.views.generic.base import View
import json
from django.http import JsonResponse
from goods.models import *
from utils.loging_decorator import login_check
# Create your views here.
from django_redis import get_redis_connection
carts_redis=get_redis_connection('carts')
from django.views.decorators.csrf import csrf_exempt
class CartVIew(View):

    def dispatch(self, request,*args, **kwargs):
        if request.method in ("POST", "DELETE"):
            cart_dict = json.loads(request.body)
            sku_id = cart_dict.get('sku_id')
            if not sku_id:
                return JsonResponse({'code': 30102, 'error': '没有sku_id参数'})
            try:
                sku = SKU.objects.get(id=sku_id)  # 11: 红袖添香
            except Exception as e:
                print(e)
                return JsonResponse({'code': 30101, 'error': "未找到商品"})
            request.cart_dict = cart_dict
            request.sku_id = sku_id
            request.sku = sku
            return super().dispatch(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)

    def post(self,request,username):
        cart_dict=request.cart_dict
        sku_id=request.sku_id
        sku=request.sku
        count = cart_dict.get('count')
        try:
            count=int(count)
        except Exception as e:
            return JsonResponse({'code': 30102, 'error': "传参不正确"})
        if count>sku.stock:
            return JsonResponse({'code': 30103, 'error': '购买数量超过库存'})
        user = request.user
        if user.username != username:
            return JsonResponse({'code': 30104, 'error': '非登录者用户'})
        redis_cart = carts_redis.hgetall('cart_%d' % user.id)  # {b'9': b'{"count": 18, "selected": 1}'}
        # 如果redis中存在 则累增
        if sku_id.encode() in redis_cart.keys():
            redis_c = carts_redis.hget('cart_%d' % user.id, sku_id)  # b'{"count": 21, "selected": 1}'
            count_r = int(json.loads(redis_c)['count'])
            count_r += count
            # 添加qi
            if count_r > sku.stock:
                return JsonResponse({'code': 30103, 'error': '购买数量超过库存'})
            status = json.dumps({'count': count_r, 'selected': 1})
            carts_redis.hset('cart_%d' % user.id, sku_id, status)
        # 否则hmset插入Redis
        else:
            # 默认都为勾选状态 1勾选 0未勾选
            status = json.dumps({'count': count, 'selected': 1})  # {"count": 21, "selected": 1}
            carts_redis.hset('cart_%d' % user.id, sku_id, status)
        skus_list = self.get_cart_list(user.id)
        return JsonResponse({'code': 200, 'data': skus_list})
    def get_cart_list(self,user_id):
        """
        获取用户的购物车数据
        :param user_id: 用户id
        :return:
        """
        cart_dict=CartVIew.get_cart_data(user_id)
        if not cart_dict:
            return []
        skus=SKU.objects.filter(id__in=cart_dict.keys())
        skus_list=[]
        for sku in skus:
            sku_data = {}
            sku_data['id'] = sku.id
            sku_data['name'] = sku.name
            sku_data['price'] = sku.price
            sku_data['default_image_url'] = str(sku.default_image_url)
            sku_data['count'] = int(cart_dict[sku.id]['count'])
            sku_data['selected'] = int(cart_dict[sku.id]['selected'])
            sku_sale_attr_name = []
            sku_sale_attr_val = []
            sale_attr_vals = SaleAttrValue.objects.filter(sku=sku)
            for sale_attr_val in sale_attr_vals:
                sku_sale_attr_val.append(sale_attr_val.sale_attr_value_name)
                sku_sale_attr_name.append(sale_attr_val.sale_attr_id.sale_attr_name)
            sku_data['sku_sale_attr_name']=sku_sale_attr_name
            sku_data['sku_sale_attr_val']=sku_sale_attr_val
            skus_list.append(sku_data)
        return skus_list

    @staticmethod
    def get_cart_data(user_id):
        cart_in_redis = carts_redis.hgetall('cart_%d' % user_id)
        if not cart_in_redis:
            return {}
        # {b"1":b"{count:1,selected:1}"}-->{1:{count:1,selected:1}}
        data={int(k):json.loads(v) for k,v in cart_in_redis.items()}
        return data

    def get(self,request,username):
        skus_list=self.get_cart_list(request.user.id)
        return JsonResponse({'code': 200, 'data': skus_list})