# AI Insight Hub - Frontend

## 快速开始

### 环境要求

- Node.js 18+
- npm 或 yarn

### 安装

```bash
# 安装依赖
npm install
```

### 运行

```bash
# 开发模式
npm run dev
```

访问：http://localhost:5173

### 构建

```bash
# 生产构建
npm run build

# 预览构建结果
npm run preview
```

## 项目结构

```
frontend/
├── src/
│   ├── main.jsx          # 入口文件
│   ├── App.jsx           # 主组件
│   ├── index.css         # 全局样式
│   ├── components/       # React 组件
│   ├── pages/            # 页面
│   ├── lib/              # 工具库
│   └── api/              # API 调用
├── public/               # 静态资源
├── index.html            # HTML 模板
├── vite.config.js        # Vite 配置
├── tailwind.config.js    # TailwindCSS 配置
├── package.json          # 依赖配置
└── README.md            # 本文件
```

## 技术栈

- React 18
- Vite 5
- TailwindCSS 3
- Axios
- Recharts
- React Router

## API 代理

开发环境下，`/api` 请求会自动代理到后端 `http://localhost:8000`

## 下一步

- [ ] 路由配置
- [ ] 组件开发
- [ ] API 集成
- [ ] 状态管理
