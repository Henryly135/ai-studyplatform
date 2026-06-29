# 前端说明

English version: [README.en.md](README.en.md)

## 技术栈

- React
- TypeScript
- Vite
- React Router

## 本地运行

```bash
cd frontend
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

如果通过完整 Docker Compose 栈运行，前端 API 配置应保持：

```env
VITE_API_BASE_URL=/api
```

## 当前路由

- `/`：公开首页。
- `/login`：登录。
- `/register/:role`：按角色注册。
- `/home`：登录后的工作区首页。
- `/home/*`：工作区子页面。
- `/ai-demo`：AI 演示页面。

## 认证行为

- 登录成功后跳转到 `/home`。
- 未登录访问 `/home` 或 `/ai-demo` 会回到公开入口。
- 退出登录会清理 `localStorage` 中的前端本地会话状态。

## 工作区结构

受保护的 `/home` 区域包含：

- 左侧导航栏。
- 顶部用户信息与退出入口。
- `/home` 概览页。
- `/home/*` 功能子页面。

功能区域展示规则配置在：

- `src/pages/Home/homeConfig.ts`
