-- 删除id=153的日常用品分类及其所有子分类
  DELETE FROM product_categories WHERE path LIKE '/153/%' OR id = 153;



  -- 确认id=153的分类已删除
  SELECT id, name, path FROM product_categories WHERE name = '日常用品' AND parent_id = 0;

  -- 查看完整的分类树结构
  SELECT
      CONCAT(REPEAT('  ', level-1), name) as 分类名称,
      id,
      parent_id,
      level,
      path
  FROM product_categories
  WHERE is_deleted = 0
  ORDER BY path;



  DELETE FROM product_categories WHERE path LIKE '/153/%' OR id = 153;



  -- 确认id=153的分类已删除
  SELECT * FROM product_categories WHERE id = 153;

  -- 确认只剩下一个日常用品一级分类
  SELECT id, name, path FROM product_categories WHERE name = '日常用品' AND parent_id = 0;

  -- 查看完整的分类树结构
  SELECT
      CONCAT(REPEAT('  ', level-1), name) as 分类名称,
      id,
      parent_id,
      level,
      path
  FROM product_categories
  WHERE is_deleted = 0
  ORDER BY path;