import colors from 'tailwindcss/colors'

/**
 * 设计 Token 事实源。
 * 取值依据 docs/05-design/01-视觉设计规范.md：
 *  - primary 即 Tailwind blue（#EFF6FF / #3B82F6 / #1D4ED8 与 blue-50/500/700 完全一致）
 *  - 断点在 Tailwind 默认基础上增加 xs；zIndex 增加 60/70（Toast、Modal 层级）
 * 若修改本文件，请同步更新 docs/05-design/01-视觉设计规范.md。
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,jsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: colors.blue,
        success: colors.green,
        warning: colors.amber,
        error: colors.red,
        info: colors.sky,
      },
      screens: {
        xs: '0px',
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'Microsoft YaHei', 'sans-serif'],
      },
      zIndex: {
        60: '60',
        70: '70',
      },
    },
  },
  plugins: [],
}
