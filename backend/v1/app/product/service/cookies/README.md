# Cookie 配置说明

## 获取淘宝 Cookie

### 方法一：浏览器导出（推荐）

1. 打开 Chrome 浏览器，登录淘宝
2. 按 F12 打开开发者工具
3. 切换到 Network（网络）标签
4. 刷新页面，点击任意请求
5. 在 Headers 中找到 `Cookie` 字段，复制整个值
6. 使用下方脚本转换为 JSON 格式

### 方法二：使用 EditThisCookie 插件

1. 安装 Chrome 插件 [EditThisCookie](https://chrome.google.com/webstore/detail/editthiscookie/fngmhnnpilhplaeedifhccceomclgfbg)
2. 登录淘宝
3. 点击插件图标 → 导出按钮
4. 粘贴到 `taobao.json` 文件

## Cookie 文件格式

将 Cookie 保存为 `cookies/taobao.json`：

```json
[
  {
    "name": "cookie_name",
    "value": "cookie_value",
    "domain": ".taobao.com",
    "path": "/"
  }
]
```

## 环境变量方式

也可以通过环境变量设置（JSON 字符串）：

```bash
export TAOBAO_COOKIES='[{"name":"xxx","value":"yyy","domain":".taobao.com","path":"/"}]'
```

## Cookie 过期

淘宝 Cookie 通常 7-30 天过期。过期后需要重新获取。

## 各平台 Cookie 文件名

- 淘宝/天猫：`cookies/taobao.json`
- 京东：`cookies/jd.json`
- 拼多多：`cookies/pdd.json`
- 抖音：`cookies/douyin.json`
