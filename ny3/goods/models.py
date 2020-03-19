from django.db import models

# Create your models here.
from utils.models import BaseModels
class Catalog(BaseModels):
    """
    商品类别
    """
    name = models.CharField(max_length=10, verbose_name='类别名称')

    class Meta:
        db_table = 'DDSC_GOODS_CATALOG'
        verbose_name = '商品类别'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class Brand(BaseModels):
    """
    品牌
    """

    name = models.CharField(max_length=20, verbose_name='商品名称')
    logo = models.ImageField(verbose_name='Logo图片')
    first_letter = models.CharField(max_length=1, verbose_name='品牌首字母')

    class Meta:
        db_table = 'DDSC_BRAND'
        verbose_name = '品牌'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class SPU(BaseModels):

    name = models.CharField(max_length=50, verbose_name='名称')
    sales = models.IntegerField(default=0, verbose_name='商品销量')
    comments = models.IntegerField(default=0, verbose_name='评价数量')
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, verbose_name='品牌')
    #进了公司 先舔  舔数据库+models
    #on_delete 级联删除 PROTECT 删除主表数据时,从表如果有主表关联的数据,则不让直接删除主表数据[开发时,尽量统一规范]
    #related_name 指定反向查询的属性名, 原反向属性名类名_set
    catalog = models.ForeignKey(Catalog, on_delete=models.PROTECT, related_name='catalog_goods', verbose_name='商品类别')

    class Meta:
        db_table = 'DDSC_SPU'
        verbose_name = 'SPU'
        verbose_name_plural = verbose_name

    def __str__(self):
        return self.name


class SPUSaleAttr(BaseModels):
    """
    SPU销售属性表
    """

    SPU_id = models.ForeignKey(SPU, on_delete=models.CASCADE, verbose_name='SPU')
    sale_attr_name = models.CharField(max_length=20, verbose_name='SPU属性名称')

    class Meta:
        db_table = 'DDSC_SPU_SALE_ATTR'
        verbose_name = 'SPU销售属性'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s' % (self.sale_attr_name)


class SKU(BaseModels):
    """
    SKU
    """
    name = models.CharField(max_length=50, verbose_name='SKU名称')
    caption = models.CharField(max_length=100, verbose_name='副标题')
    SPU_ID = models.ForeignKey(SPU, on_delete=models.CASCADE, verbose_name='商品')
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='单价')
    cost_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='进价')
    market_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='市场价')
    stock = models.IntegerField(default=0, verbose_name='库存')
    sales = models.IntegerField(default=0, verbose_name='销量')
    comments = models.IntegerField(default=0, verbose_name='评价数')
    is_launched = models.BooleanField(default=True, verbose_name='是否上架销售')
    #该字段将图片存储至 指定文件夹 -> settings.MEDIA_ROOT + upload_to参数的值 ,且该字段对应的值为图片在服务器上的存储路径  var/a.jpg
    #  BASE_DIR + media/sku_default/
    default_image_url = models.ImageField(upload_to='sku_default/',  verbose_name='默认图片', default=None)

    class Meta:
        db_table = 'DDSC_SKU'
        verbose_name = 'SKU表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s: %s' % (self.id, self.name)


class SaleAttrValue(BaseModels):
    """
    销售属性值表
    """

    sale_attr_id = models.ForeignKey(SPUSaleAttr, on_delete=models.CASCADE, verbose_name='销售属性id')
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, verbose_name='sku', default='')
    sale_attr_value_name = models.CharField(max_length=20, verbose_name='销售属性值名称')

    class Meta:
        db_table = 'DDSC_SALE_ATTR_VALUE'
        verbose_name = '销售属性值'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s - %s' % (self.sale_attr_id, self.sale_attr_value_name)


class SKUImage(BaseModels):
    """
    SKU图片
    """

    sku_id = models.ForeignKey(SKU, on_delete=models.CASCADE, verbose_name='sku')
    image = models.ImageField(verbose_name='图片路径')

    class Meta:
        db_table = 'DDSC_SKU_IMAGE'
        verbose_name = 'SKU图片'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s %s' % (self.sku_id.name, self.id)


class SPUSpec(BaseModels):
    """
    SPU规格表
    """

    spu = models.ForeignKey(SPU, on_delete=models.CASCADE, verbose_name='SPU')
    spec_name = models.CharField(max_length=20, verbose_name='SPU规格名称')

    class Meta:
        db_table = 'DDSC_SPU_SPEC'
        verbose_name = 'SPU规格'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s: %s' % (self.spu.name, self.spec_name)


class SKUSpecValue(BaseModels):
    """
    SKU规格属性表
    """
    sku = models.ForeignKey(SKU, on_delete=models.CASCADE, verbose_name='sku')
    spu_spec = models.ForeignKey(SPUSpec, on_delete=models.CASCADE, verbose_name='SPU规格名称')
    name = models.CharField(max_length=20, verbose_name='SKU规格名称值')

    class Meta:
        db_table = 'DDSC_SKU_SPEC_VALUE'
        verbose_name = 'SKU规格属性值表'
        verbose_name_plural = verbose_name

    def __str__(self):
        return '%s: %s: %s' % (self.sku, self.spu_spec.spec_name, self.name)
