import toast from 'react-hot-toast'

const BASE_OPTIONS = {
  duration: 3000,
}

/**
 * 全局消息提示（02 §4.1）：复用 react-hot-toast，不自研 Toast 组件。
 * 成功 3s、错误 5s，loading 需手动 dismiss。
 */
export const notify = {
  /**
   * @param {string} message
   * @param {import('react-hot-toast').ToastOptions} [options]
   */
  success: (message, options = {}) => toast.success(message, { ...BASE_OPTIONS, ...options }),

  /**
   * @param {string} message
   * @param {import('react-hot-toast').ToastOptions} [options]
   */
  error: (message, options = {}) =>
    toast.error(message, { ...BASE_OPTIONS, duration: 5000, ...options }),

  /**
   * @param {string} message
   * @param {import('react-hot-toast').ToastOptions} [options]
   * @returns {string} toast id，用于 dismiss
   */
  loading: (message, options = {}) => toast.loading(message, { ...BASE_OPTIONS, ...options }),

  /** @param {string} [id] */
  dismiss: id => toast.dismiss(id),
}
