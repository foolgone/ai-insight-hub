import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

/**
 * Vitest 配置（前端单元/组件测试）
 * 与 docs/06-testing/04-前端测试规范.md §4.1 保持一致。
 *
 * - 与 vite.config.js 分离，避免测试专属配置污染构建配置
 * - jsdom 提供浏览器环境；setup 文件注册 jest-dom 断言与 matchMedia mock
 * - globals: false —— 用例中显式 import { test, expect, vi }
 */
export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.js'],
    include: ['src/**/*.{test,spec}.{js,jsx}'],
    globals: false,
    clearMocks: true,
    restoreMocks: true,
    // 骨架阶段还没有用例，避免 vitest run 以「No test files found」失败；用例补齐后可删除
    passWithNoTests: true,
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html', 'lcov'],
      reportsDirectory: './coverage',
      include: ['src/**/*.{js,jsx}'],
      exclude: [
        'src/main.jsx',
        'src/test/**',
        'src/**/*.test.{js,jsx}',
        'src/**/*.spec.{js,jsx}',
      ],
      // ⚠️ 键名是 thresholds（不是 coverageThresholds）
      thresholds: {
        lines: 80,
        functions: 80,
        statements: 80,
        branches: 70,
      },
    },
  },
})
