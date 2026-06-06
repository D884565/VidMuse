#!/usr/bin/env python3
"""
插入商品分类数据脚本
执行此脚本将向product_categories表中插入常见的电商分类数据，包含三级分类结构
"""
import sys
import os
from typing import Dict, List

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from backend.v1.app.product.service.product_category_service import ProductCategoryService
from backend.v1.app.product.dao.schema import CategoryCreateRequest
from backend.v1.app.config.config import settings

# 创建数据库会话
engine = create_engine(settings.db_url.replace("+asyncmy", ""))
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 分类数据定义：一级分类 -> 二级分类 -> 三级分类
CATEGORY_DATA: Dict[str, Dict[str, List[str]]] = {
    "美食饮品": {
        "休闲零食": ["饼干糕点", "坚果炒货", "糖果巧克力", "肉干肉脯", "蜜饯果干", "膨化食品"],
        "方便速食": ["方便面", "自热食品", "冲泡饮品", "速冻食品", "罐头食品", "火腿肠"],
        "粮油调味": ["食用油", "米面杂粮", "调味品", "干货", "酱类", "火锅底料"],
        "饮料冲调": ["饮用水", "碳酸饮料", "果汁饮料", "咖啡奶茶", "茶饮", "功能饮料"],
        "生鲜食品": ["水果", "蔬菜", "肉类", "海鲜", "禽蛋", "乳制品"]
    },
    "美妆护肤": {
        "护肤": ["洁面", "爽肤水", "乳液面霜", "面膜", "精华", "眼霜", "防晒", "护手霜"],
        "彩妆": ["底妆", "眼妆", "唇妆", "腮红修容", "卸妆", "化妆工具"],
        "香水香氛": ["男士香水", "女士香水", "中性香水", "香薰", "身体喷雾"],
        "个人护理": ["洗发护发", "沐浴露", "牙膏牙刷", "身体乳", "洗手液", "卫生巾"]
    },
    "服饰鞋包": {
        "男装": ["T恤", "衬衫", "裤子", "外套", "内衣", "毛衣", "卫衣", "夹克"],
        "女装": ["连衣裙", "上衣", "裤子", "裙子", "内衣", "毛衣", "卫衣", "风衣"],
        "鞋靴": ["男鞋", "女鞋", "运动鞋", "休闲鞋", "靴子", "凉鞋", "拖鞋"],
        "箱包": ["手提包", "双肩包", "钱包", "行李箱", "斜挎包", "腰包"]
    },
    "数码家电": {
        "手机通讯": ["手机", "手机配件", "充电器", "耳机", "数据线", "手机壳"],
        "电脑办公": ["笔记本", "台式机", "平板电脑", "办公设备", "键盘鼠标", "显示器"],
        "家用电器": ["大家电", "生活电器", "厨房电器", "个人护理电器", "影音娱乐"],
        "数码配件": ["相机", "摄影器材", "智能设备", "存储设备", "智能手表", "耳机音响"]
    },
    "家居生活": {
        "家具": ["沙发", "床", "桌子", "椅子", "柜子", "茶几"],
        "家居装饰": ["摆件", "装饰画", "窗帘", "地毯", "墙纸", "灯饰"],
        "家纺": ["床上用品", "毛巾浴巾", "抱枕靠垫", "地毯地垫", "窗帘", "沙发套"],
        "日用百货": ["清洁用品", "收纳用品", "餐具", "厨具", "洗浴用品", "一次性用品"]
    },
    "母婴用品": {
        "奶粉辅食": ["婴儿奶粉", "辅食", "营养品", "零食"],
        "尿裤湿巾": ["纸尿裤", "拉拉裤", "湿巾", "纸巾"],
        "喂养用品": ["奶瓶", "奶嘴", "吸奶器", "餐具", "暖奶器"],
        "童车童床": ["婴儿车", "安全座椅", "婴儿床", "餐椅", "玩具"]
    },
    "运动户外": {
        "运动服饰": ["运动套装", "运动T恤", "运动裤", "运动鞋", "运动外套"],
        "健身器材": ["跑步机", "哑铃", "健身车", "瑜伽用品", "拉力器"],
        "户外装备": ["帐篷", "睡袋", "登山包", "户外鞋", "烧烤用具"],
        "球类运动": ["篮球", "足球", "羽毛球", "乒乓球", "排球"]
    }
}


def create_categories(db: Session):
    """
    递归创建分类
    """
    created_count = 0
    skipped_count = 0

    # 遍历一级分类
    for level1_name, level2_data in CATEGORY_DATA.items():
        # 创建一级分类
        try:
            level1_request = CategoryCreateRequest(
                name=level1_name,
                parent_id=0,
                sort=100
            )
            level1_category = ProductCategoryService.create_category(db, level1_request)
            print(f"创建一级分类: {level1_name} (ID: {level1_category.id})")
            created_count += 1

            # 遍历二级分类
            for level2_name, level3_list in level2_data.items():
                try:
                    level2_request = CategoryCreateRequest(
                        name=level2_name,
                        parent_id=level1_category.id,
                        sort=100
                    )
                    level2_category = ProductCategoryService.create_category(db, level2_request)
                    print(f"  创建二级分类: {level2_name} (ID: {level2_category.id})")
                    created_count += 1

                    # 遍历三级分类
                    for level3_name in level3_list:
                        try:
                            level3_request = CategoryCreateRequest(
                                name=level3_name,
                                parent_id=level2_category.id,
                                sort=100
                            )
                            level3_category = ProductCategoryService.create_category(db, level3_request)
                            print(f"    创建三级分类: {level3_name} (ID: {level3_category.id})")
                            created_count += 1
                        except ValueError as e:
                            if "已存在" in str(e):
                                print(f"    三级分类已存在: {level3_name}, 跳过")
                                skipped_count += 1
                            else:
                                print(f"    创建三级分类失败: {level3_name}, 错误: {e}")
                except ValueError as e:
                    if "已存在" in str(e):
                        print(f"  二级分类已存在: {level2_name}, 跳过")
                        skipped_count += 1
                    else:
                        print(f"  创建二级分类失败: {level2_name}, 错误: {e}")
        except ValueError as e:
            if "已存在" in str(e):
                print(f"一级分类已存在: {level1_name}, 跳过")
                skipped_count += 1
            else:
                print(f"创建一级分类失败: {level1_name}, 错误: {e}")

    print(f"\n分类插入完成:")
    print(f"   成功创建: {created_count} 个分类")
    print(f"   已存在跳过: {skipped_count} 个分类")

    # 打印分类树
    print(f"\n当前分类树结构:")
    category_tree = ProductCategoryService.get_category_tree(db)
    for level1 in category_tree:
        print(f"{level1.name} (ID: {level1.id}, 路径: {level1.path})")
        for level2 in level1.children:
            print(f"  {level2.name} (ID: {level2.id}, 路径: {level2.path})")
            for level3 in level2.children:
                print(f"    {level3.name} (ID: {level3.id}, 路径: {level3.path})")


if __name__ == "__main__":
    print("开始插入商品分类数据...")
    print(f"将插入 {len(CATEGORY_DATA)} 个一级分类，及其二级、三级分类\n")

    db = SessionLocal()
    try:
        create_categories(db)
    finally:
        db.close()

    print("\n脚本执行完成!")
