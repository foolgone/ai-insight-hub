/**
 * 设计 Token 事实源（Editorial Data Terminal）。
 *
 * 方向：编辑部风格的数据终端 —— 暖纸底、墨色侧栏、衬线标题、
 * 等宽标签、朱砂色作为唯一强调色、细线分隔、几乎不用阴影。
 *
 * 说明：`primary` 仍是全局强调色（历史代码大量使用 primary-*），
 * 这里把它映射为朱砂色，而不是 Tailwind 默认蓝，避免整站「SaaS 模板感」。
 */
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#F8E9E3',
          100: '#F1D6CC',
          200: '#E4B4A4',
          300: '#D8917B',
          400: '#CE6A4E',
          500: '#C8452A',
          600: '#B23C24',
          700: '#8F2F1B',
          800: '#6E2414',
          900: '#4F1A0E',
        },
        // 暖灰：替代 Tailwind 默认冷灰，整站底色随之变暖
        gray: {
          50: '#FAF8F3',
          100: '#F3F0E8',
          200: '#E7E2D6',
          300: '#D5CFC0',
          400: '#A8A296',
          500: '#7C776A',
          600: '#5E594D',
          700: '#3A382E',
          800: '#26241C',
          900: '#17160F',
        },
        success: {
          50: '#EAF0EA',
          100: '#D7E3D8',
          200: '#B5CBB8',
          300: '#8FB097',
          400: '#5F8A6B',
          500: '#3E6B4F',
          600: '#355C43',
          700: '#2A4A36',
        },
        warning: {
          50: '#F6EFDF',
          100: '#EDE1C6',
          200: '#DECBA0',
          300: '#C9AE72',
          400: '#B8924A',
          500: '#A8792A',
          600: '#8F6520',
          700: '#6F4E18',
        },
        error: {
          50: '#F7E6E1',
          100: '#EFD0C8',
          200: '#E0AFA3',
          300: '#CE8577',
          400: '#B85A4B',
          500: '#A33A2E',
          600: '#8A3026',
          700: '#6B251D',
        },
        info: {
          50: '#E8EEF0',
          100: '#D3E0E4',
          200: '#AEC4CB',
          300: '#84A5AF',
          400: '#5C8492',
          500: '#3D5A6C',
          600: '#334C5C',
          700: '#273B48',
        },
      },
      fontFamily: {
        sans: ['Inter', 'PingFang SC', 'HarmonyOS Sans SC', 'Microsoft YaHei', 'sans-serif'],
        display: [
          '"Noto Serif SC"',
          '"Source Han Serif SC"',
          '"Songti SC"',
          'STSong',
          'SimSun',
          'Georgia',
          'serif',
        ],
        mono: ['"JetBrains Mono"', '"SFMono-Regular"', 'Consolas', '"Liberation Mono"', 'monospace'],
      },
      borderRadius: {
        none: '0',
        sm: '1px',
        DEFAULT: '2px',
        md: '2px',
        lg: '3px',
        xl: '4px',
        '2xl': '6px',
        full: '9999px',
      },
      boxShadow: {
        sm: '0 1px 0 rgba(23, 22, 15, 0.04)',
        DEFAULT: '0 1px 2px rgba(23, 22, 15, 0.05)',
        md: '0 8px 24px -12px rgba(23, 22, 15, 0.18)',
        lg: '0 16px 40px -20px rgba(23, 22, 15, 0.25)',
        xl: '0 24px 60px -30px rgba(23, 22, 15, 0.35)',
      },
      screens: {
        xs: '0px',
      },
      zIndex: {
        60: '60',
        70: '70',
      },
    },
  },
  plugins: [],
}
