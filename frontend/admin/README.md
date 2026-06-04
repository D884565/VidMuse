# VidMuse 后台管理系统

## 开发环境运行
```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问地址：http://localhost:5173

## 生产环境构建
```bash
# 构建生产版本
npm run build

# 预览构建结果
npm run preview
```

构建产物会生成在 `dist` 目录下。

## 部署说明

### 1. 环境变量配置
根据部署环境修改 `.env.production` 中的 `VITE_API_BASE_URL` 为实际的后端API地址。

### 2. Nginx 配置示例
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态资源
    location / {
        root /path/to/admin/dist;
        try_files $uri $uri/ /index.html;
        index index.html;
    }

    # API接口代理
    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    # 安全配置
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
}
```

### 3. Docker 部署（可选）
可以使用以下Dockerfile进行容器化部署：
```dockerfile
FROM node:18-alpine as builder
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

## 技术栈
- Vue 3 (Composition API)
- Vite
- Element Plus
- Pinia (状态管理)
- Vue Router (路由)
- Axios (HTTP请求)
- ECharts (数据可视化)
- dayjs (日期处理)

## 功能模块
- ✅ 统计概览：调用量统计、成功率、耗时分析、异常监控
- ✅ 轨迹管理：轨迹列表、多条件筛选、搜索、导出
- ✅ 轨迹详情：完整推理链路展示、时间线、原始JSON查看
- ✅ 权限控制：管理员登录、路由守卫、接口权限校验
- ✅ 响应式设计：适配主流屏幕分辨率
