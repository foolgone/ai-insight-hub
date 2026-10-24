# AI Insight Hub - Frontend

## 快速开始

### 环境要求

- Node.js 20+
- npm 10+

### 安装

```bash
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
│   ├── App.jsx           # 主组件（当前为后端连通性欢迎页）
│   ├── index.css         # 全局样式
│   ├── components/       # 规划：通用组件
│   ├── pages/            # 规划：页面
│   ├── api/              # 规划：API 调用
│   ├── stores/           # 规划：Zustand stores
│   ├── hooks/            # 规划：自定义 Hooks
│   └── lib/              # 规划：工具库
├── tests/                # 规划：测试
├── public/               # 静态资源
├── index.html            # HTML 模板
├── vite.config.js        # Vite 配置（/api 代理到后端）
├── tailwind.config.js    # TailwindCSS 配置（设计 Token 事实源）
├── .eslintrc.json        # ESLint 配置
├── package.json          # 依赖与脚本
└── README.md             # 本文件
```

## 技术栈

- React 18
- Vite 5
- TailwindCSS 3
- React Router 6（已安装，路由待实现）
- React Query v5（服务端状态）
- Zustand 4（客户端状态）
- Axios
- Recharts
- Vitest + @testing-library/react（测试）

## 设计 Token

`tailwind.config.js` 是设计 Token 的事实源，已按 `docs/05-design/01-视觉设计规范.md` 落地：

- 颜色：`primary`（= Tailwind blue）、`success` / `warning` / `error` / `info`
- 断点：在默认基础上增加 `xs: 0px`
- 层级：`z-60` / `z-70`
- 字体：`Inter` / `PingFang SC` / `Microsoft YaHei`

改设计 token 时请同时更新该配置文件与视觉规范文档。

## 测试

```bash
npm run test            # Vitest（watch 模式）
npm run test:ui         # Vitest UI
npm run test:coverage   # 覆盖率
```

## API 代理

开发环境下，`/api` 请求会自动代理到后端 `http://localhost:8000`（见 `vite.config.js`），因此前端代码里直接用相对路径即可：

```js
fetch('/api/v1/health')
```

## 下一步

- [ ] 路由骨架（React Router 6）
- [ ] 登录页 / 注册页
- [ ] 数据源管理页
- [ ] 质量评估页
- [ ] 知识库页
- [ ] 洞察分析页
- [ ] 报告列表与详情页
- [ ] 组件库实现（见 `docs/05-design/02-组件库设计规范.md`）
