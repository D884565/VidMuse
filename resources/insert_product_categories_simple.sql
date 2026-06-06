-- 简化版商品分类数据SQL脚本
-- 仅包含3个一级分类：美食饮品、美妆护肤、数码家电

-- 先禁用外键检查
SET FOREIGN_KEY_CHECKS = 0;

-- ------------------------------
-- 一级分类
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('美食饮品', 0, 1, '/1/', 100, 0),
('美妆护肤', 0, 1, '/2/', 100, 0),
('数码家电', 0, 1, '/3/', 100, 0);

-- ------------------------------
-- 二级分类 - 美食饮品 (parent_id=1)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('休闲零食', 1, 2, '/1/4/', 100, 0),
('方便速食', 1, 2, '/1/5/', 100, 0),
('饮料冲调', 1, 2, '/1/6/', 100, 0);

-- ------------------------------
-- 三级分类 - 休闲零食 (parent_id=4)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('饼干糕点', 4, 3, '/1/4/7/', 100, 0),
('坚果炒货', 4, 3, '/1/4/8/', 100, 0),
('糖果巧克力', 4, 3, '/1/4/9/', 100, 0),
('肉干肉脯', 4, 3, '/1/4/10/', 100, 0);

-- ------------------------------
-- 三级分类 - 方便速食 (parent_id=5)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('方便面', 5, 3, '/1/5/11/', 100, 0),
('自热食品', 5, 3, '/1/5/12/', 100, 0),
('冲泡饮品', 5, 3, '/1/5/13/', 100, 0),
('速冻食品', 5, 3, '/1/5/14/', 100, 0);

-- ------------------------------
-- 三级分类 - 饮料冲调 (parent_id=6)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('饮用水', 6, 3, '/1/6/15/', 100, 0),
('碳酸饮料', 6, 3, '/1/6/16/', 100, 0),
('果汁饮料', 6, 3, '/1/6/17/', 100, 0),
('咖啡奶茶', 6, 3, '/1/6/18/', 100, 0);

-- ------------------------------
-- 二级分类 - 美妆护肤 (parent_id=2)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('护肤', 2, 2, '/2/19/', 100, 0),
('彩妆', 2, 2, '/2/20/', 100, 0),
('个人护理', 2, 2, '/2/21/', 100, 0);

-- ------------------------------
-- 三级分类 - 护肤 (parent_id=19)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('洁面', 19, 3, '/2/19/22/', 100, 0),
('爽肤水', 19, 3, '/2/19/23/', 100, 0),
('乳液面霜', 19, 3, '/2/19/24/', 100, 0),
('面膜', 19, 3, '/2/19/25/', 100, 0),
('防晒', 19, 3, '/2/19/26/', 100, 0);

-- ------------------------------
-- 三级分类 - 彩妆 (parent_id=20)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('底妆', 20, 3, '/2/20/27/', 100, 0),
('眼妆', 20, 3, '/2/20/28/', 100, 0),
('唇妆', 20, 3, '/2/20/29/', 100, 0),
('卸妆', 20, 3, '/2/20/30/', 100, 0);

-- ------------------------------
-- 三级分类 - 个人护理 (parent_id=21)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('洗发护发', 21, 3, '/2/21/31/', 100, 0),
('沐浴露', 21, 3, '/2/21/32/', 100, 0),
('牙膏牙刷', 21, 3, '/2/21/33/', 100, 0),
('身体乳', 21, 3, '/2/21/34/', 100, 0);

-- ------------------------------
-- 二级分类 - 数码家电 (parent_id=3)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('手机通讯', 3, 2, '/3/35/', 100, 0),
('电脑办公', 3, 2, '/3/36/', 100, 0),
('数码配件', 3, 2, '/3/37/', 100, 0);

-- ------------------------------
-- 三级分类 - 手机通讯 (parent_id=35)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('手机', 35, 3, '/3/35/38/', 100, 0),
('手机配件', 35, 3, '/3/35/39/', 100, 0),
('充电器', 35, 3, '/3/35/40/', 100, 0),
('耳机', 35, 3, '/3/35/41/', 100, 0);

-- ------------------------------
-- 三级分类 - 电脑办公 (parent_id=36)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('笔记本', 36, 3, '/3/36/42/', 100, 0),
('平板电脑', 36, 3, '/3/36/43/', 100, 0),
('键盘鼠标', 36, 3, '/3/36/44/', 100, 0),
('显示器', 36, 3, '/3/36/45/', 100, 0);

-- ------------------------------
-- 三级分类 - 数码配件 (parent_id=37)
-- ------------------------------
INSERT INTO product_categories (name, parent_id, level, path, sort, is_deleted) VALUES
('耳机音响', 37, 3, '/3/37/46/', 100, 0),
('智能设备', 37, 3, '/3/37/47/', 100, 0),
('存储设备', 37, 3, '/3/37/48/', 100, 0),
('智能手表', 37, 3, '/3/37/49/', 100, 0);

-- 恢复外键检查
SET FOREIGN_KEY_CHECKS = 1;

-- 验证插入结果
SELECT '总分类数' as type, COUNT(*) as count FROM product_categories WHERE is_deleted = 0
UNION ALL
SELECT CONCAT('Level ', level, '级分类数') as type, COUNT(*) as count FROM product_categories WHERE is_deleted = 0 GROUP BY level ORDER BY type;
