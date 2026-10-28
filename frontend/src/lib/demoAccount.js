/** 演示账号（登录页提示与弹窗文案共用；不在组件里散落字符串）。 */
export const DEMO_ACCOUNT = {
  email: 'demo@example.com',
  password: 'demo123',
}

// 注意：文案里不要出现“注册”二字——前端无注册页，招聘者按提示也注册不了。
export const DEMO_MODAL_NOTICE =
  '演示账号仅供浏览；运行 AI 任务需要配置自己的 DeepSeek Key（演示账号不预置 Key）。'

export function isDemoUser(user) {
  return user?.email === DEMO_ACCOUNT.email
}
