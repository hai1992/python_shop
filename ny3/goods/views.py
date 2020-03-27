import json

from django.conf import settings
from django.core.paginator import Paginator
from django.shortcuts import render
# Create your views here.
from django.views.generic.base import View
from django.http import JsonResponse
from .models import *
from django_redis import get_redis_connection
goods_redis = get_redis_connection('goods')
class GoodsIndexView(View):
    def get(self,request):
        """
        首页商品及分类项展示
        商城默认有三个品类：
        名称         id
        拉杆箱        101
        背包         102
        手提包       103
        :param result:
        :return:
        """
        data=goods_redis.get('index_cache')
        if data:
            # 走缓存
            result={'code':200,'data':json.loads(data),'base_url': settings.PIC_URL}
            return JsonResponse(result)
        # 不走缓存,获取所有商品类别
        catalog_list = Catalog.objects.all()
        # 找到所有商品类别下的3个sku
        index_data=[]
        for catalog in catalog_list:
            cata_dict={}
            cata_dict['catalog_id'] = catalog.id
            cata_dict['catalog_name'] = catalog.name
            cata_dict['sku'] = []
        #     获取该品类下的sku
            spu_ids=catalog.catalog_goods.values('id')
            sku_list=SKU.objects.filter(SPU_ID__in=spu_ids,is_launched=True)[:3]
            for sku in sku_list:
                sku_dict={}
                sku_dict['skuid'] = sku.id
                sku_dict['caption'] = sku.caption
                sku_dict['price'] = str(sku.price)
                sku_dict['name'] = sku.name
                # 图片字段属性
                sku_dict['image'] = str(sku.default_image_url)
                cata_dict['sku'].append(sku_dict)
            index_data.append(cata_dict)
        # 将查询结果 入缓存 ?时间
        goods_redis.set("index_cache", json.dumps(index_data))
        result = {'code': 200, 'data': index_data, 'base_url': settings.PIC_URL}
        return JsonResponse(result)
class GoodsDetailView(View):
    def get(self,request,sku_id):
        """
        获取sku详情页信息，获取图片暂未完成
        :param request:
        :param sku_id: sku的id
        :return:
        """
        sku_res=goods_redis.get('goods_%s'%sku_id)
        if sku_res:
            result = {'code': 200, 'data': json.loads(sku_res), 'base_url': settings.PIC_URL}
            return JsonResponse(result)
        print(1)
        try:
            sku_item=SKU.objects.get(id=sku_id)
        except:
            result = {'code': 40300, 'error': "Such sku doesn' exist", }
            return JsonResponse(result)
        else:
            sku_res={}
            print(1)
            sku_catalog=sku_item.SPU_ID.catalog
            sku_res['image']=str(sku_item.default_image_url)
            sku_res['caption']=sku_item.caption
            sku_res['price']=str(sku_item.price)
            sku_res['spu']=sku_item.SPU_ID.id
            sku_res['name']=sku_item.name
            sku_res['catalog_id']=sku_catalog.id
            sku_res['catalog_name']=sku_catalog.name
            sku_image=SKUImage.objects.filter(sku_id=sku_item)
            if sku_image:
                sku_res['detail_image'] = str(sku_image[0].image)
            else:
                sku_res['detail_image'] = ""
            sale_attr_vals=SaleAttrValue.objects.filter(sku=sku_item)
            sku_sale_attr_id=[]
            sku_sale_attr_names=[]
            sku_sale_attr_val_id=[]
            sku_sale_attr_val_names=[]
            sku_all_sale_attr_vals_id={}
            sku_all_sale_attr_vals_name={}
            for sale_attr_val in sale_attr_vals:
                sku_sale_attr_id.append(sale_attr_val.sale_attr_id.id)
                sku_sale_attr_names.append(sale_attr_val.sale_attr_id.sale_attr_name)
                sku_sale_attr_val_id.append(sale_attr_val.id)
                sku_sale_attr_val_names.append(sale_attr_val.sale_attr_value_name)
                attr_id=sale_attr_val.sale_attr_id.id
                attr_vals=SaleAttrValue.objects.filter(sale_attr_id=attr_id)
                sku_all_sale_attr_vals_id[int(attr_id)]=[]
                sku_all_sale_attr_vals_name[int(attr_id)]=[]
                for val in attr_vals:
                    sku_all_sale_attr_vals_id[int(attr_id)].append(val.id)
                    sku_all_sale_attr_vals_name[int(attr_id)].append(val.sale_attr_value_name)
            sku_res['sku_sale_attr_id']=sku_sale_attr_id
            sku_res['sku_sale_attr_names']=sku_sale_attr_names
            sku_res['sku_sale_attr_val_id']=sku_sale_attr_val_id
            sku_res['sku_sale_attr_val_names']=sku_sale_attr_val_names
            sku_res['sku_all_sale_attr_vals_id']=sku_all_sale_attr_vals_id
            sku_res['sku_all_sale_attr_vals_name']=sku_all_sale_attr_vals_name
            # 查找规格属性值
            sku_spec_values = SKUSpecValue.objects.filter(sku=sku_id)
            if not sku_spec_values:
                sku_res['spec'] = dict()
            else:
                spec={}
                for sku_spec_value in sku_spec_values:
                    spec[sku_spec_value.spu_spec.spec_name] = sku_spec_value.name
                sku_res['spec'] = spec
            goods_redis.setex('goods_%s'%sku_id,3600*24,json.dumps(sku_res))
            print(sku_res)
            result = {'code': 200, 'data': sku_res, 'base_url': settings.PIC_URL}
            return JsonResponse(result)

class GoodsListView(View):
    def get(self,request,catalog_id):
        """
        获取列表页内容
        :param request:
        :param catalog_id: 分类id
        :param page_num: 第几页
        :param page_size: 每页显示多少项
        :return:
        """
        # 127.0.0.1:8000/v1/goods/catalogs/1/?launched=true&page=1
        # 0. 获取url传递参数值
        launched = bool(request.GET.get('launched', True))
        page_num = request.GET.get('page', 1)
        # 获取分类下的sku
        spu_list = SPU.objects.filter(catalog=catalog_id).values('id')
        sku_list = SKU.objects.filter(SPU_ID__in=spu_list,is_launched=launched).order_by('id')
        # 分页
        page_num = int(page_num)
        page_size=9
        try:
            paginator = Paginator(sku_list, page_size)
            if page_num > paginator.num_pages:
                page_num = paginator.num_pages
            elif page_num < 1:
                page_num = 1
            # 获取指定页码的数据
            page_skus = paginator.page(page_num)
            page_skus_json = []
            for sku in page_skus:
                sku_dict = dict()
                sku_dict['skuid'] = sku.id
                sku_dict['name'] = sku.name
                sku_dict['price'] = str(sku.price)
                sku_dict['image'] = str(sku.default_image_url)
                page_skus_json.append(sku_dict)
        except:
            result = {'code': 40200, 'error': '页数有误，小于0或者大于总页数'}
            return JsonResponse(result)
        result = {'code': 200, 'data': page_skus_json,
                  'paginator': {'pagesize': page_size, 'total': len(sku_list)}, 'base_url': settings.PIC_URL}
        return JsonResponse(result)

class GoodsChangeSkuView(View):
    def post(self,request):
        data = json.loads(request.body)
        # 将前端传来的销售属性值id放入列表
        sku_vals = []
        result = {}
        for k in data:
            if 'spuid' != k:
                sku_vals.append(data[k])
        print('sku_vals',sku_vals)
        sku_list = SKU.objects.filter(SPU_ID=data['spuid'])
        for sku in sku_list:
            sku_details = dict()
            sku_details['sku_id'] = sku.id
            # 获取sku销售属性值id
            sale_attrs_val_lists = SaleAttrValue.objects.filter(sku=sku.id)
            sale_attr_val_id = []
            for sale_attrs_val in sale_attrs_val_lists:
                sale_attr_val_id.append(sale_attrs_val.id)
            print('sale_attr_val_id',sale_attr_val_id)
            if sku_vals in sale_attr_val_id:
                result = {"code": 200, "data": sku.id, }
        if len(result) == 0:
            result = {"code": 40050, "error": "no such sku", }
        return JsonResponse(result)



