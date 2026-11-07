import { useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { Button } from '../../components/Button'
import { Checkbox } from '../../components/Checkbox'
import { Input } from '../../components/Input'
import { useAuth } from '../../hooks/useAuth'
import { DEMO_ACCOUNT } from '../../lib/demoAccount'
import { getErrorMessage } from '../../lib/errorMessages'
import { notify } from '../../lib/toast'

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const CAPABILITIES = [
  { index: '01', label: '清洗', note: '去重、补全、结构化' },
  { index: '02', label: '评估', note: '5 维质量与人工复核' },
  { index: '03', label: '洞察', note: '意图、情感与痛点' },
]

export default function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { login } = useAuth()

  const [form, setForm] = useState({ email: '', password: '' })
  const [remember, setRemember] = useState(true)
  const [errors, setErrors] = useState({})
  const [submitting, setSubmitting] = useState(false)

  const prefillDemo = () => {
    setForm({ email: DEMO_ACCOUNT.email, password: DEMO_ACCOUNT.password })
    setErrors({})
    // 不自动提交：让访客自己点登录
  }

  const updateField = (field, value) => {
    setForm(current => ({ ...current, [field]: value }))
    setErrors(current => ({ ...current, [field]: undefined, form: undefined }))
  }

  const validate = () => {
    const nextErrors = {}
    if (!form.email.trim()) nextErrors.email = '请输入邮箱'
    else if (!EMAIL_PATTERN.test(form.email.trim())) nextErrors.email = '邮箱格式不正确'
    if (!form.password) nextErrors.password = '请输入密码'
    setErrors(nextErrors)
    return Object.keys(nextErrors).length === 0
  }

  const handleSubmit = async event => {
    event.preventDefault()
    if (submitting || !validate()) return

    setSubmitting(true)
    try {
      await login({ email: form.email.trim(), password: form.password, remember })
      notify.success('登录成功')
      const returnUrl = searchParams.get('returnUrl')
      const target = returnUrl && returnUrl.startsWith('/') ? returnUrl : '/dashboard'
      navigate(target, { replace: true })
    } catch (error) {
      const message = getErrorMessage(error)
      setErrors({ form: message })
      notify.error(message)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="grid min-h-screen bg-gray-50 lg:grid-cols-[1.05fr_0.95fr]">
      {/* 左：编辑部式主张面板 */}
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-gray-900 p-12 text-gray-100 lg:flex">
        <div className="grid-paper pointer-events-none absolute inset-0 opacity-70" aria-hidden="true" />
        <div className="relative flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center border border-white/25 font-display text-[13px] leading-none text-gray-50">
            AI
          </div>
          <div>
            <p className="font-display text-[15px] leading-tight text-gray-50">AI Insight Hub</p>
            <p className="mt-0.5 font-mono text-[9px] uppercase tracking-[0.22em] text-gray-500">
              Conversation Intelligence
            </p>
          </div>
        </div>

        <div className="relative max-w-xl">
          <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-primary-400">
            Customer conversation intelligence
          </p>
          <h1 className="mt-6 font-display text-[52px] font-normal leading-[1.08] tracking-tight text-gray-50">
            把对话，
            <br />
            变成可读的信号<span className="text-primary-500">。</span>
          </h1>
          <p className="mt-6 max-w-md text-sm leading-relaxed text-gray-400">
            从原始客服对话到质量评估、知识沉淀与经营洞察——一条可回溯的数据链路，
            让每一个结论都有据可查。
          </p>
        </div>

        <div className="relative grid grid-cols-3 gap-6 border-t border-white/10 pt-6">
          {CAPABILITIES.map(item => (
            <div key={item.index}>
              <p className="font-mono text-[10px] tracking-[0.18em] text-gray-600">{item.index}</p>
              <p className="mt-2 font-display text-lg text-gray-100">{item.label}</p>
              <p className="mt-1 text-[11px] leading-relaxed text-gray-500">{item.note}</p>
            </div>
          ))}
        </div>
      </aside>

      {/* 右：登录表单 */}
      <main className="flex flex-col justify-center px-6 py-12 sm:px-12 lg:px-16">
        <div className="mx-auto w-full max-w-[380px]">
          <div className="mb-10 flex items-center gap-3 lg:hidden">
            <div className="grid h-9 w-9 place-items-center border border-gray-900 font-display text-[13px] leading-none text-gray-900">
              AI
            </div>
            <span className="font-display text-base text-gray-900">AI Insight Hub</span>
          </div>

          <p className="eyebrow">Sign in / 登录</p>
          <h2 className="mt-3 font-display text-3xl font-normal tracking-tight text-gray-900">
            欢迎回来
          </h2>
          <p className="mt-2 text-sm text-gray-600">使用管理员分配的账号进入工作台。</p>

          <form onSubmit={handleSubmit} noValidate className="mt-8 space-y-5">
            {errors.form ? (
              <div
                role="alert"
                className="border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
              >
                {errors.form}
              </div>
            ) : null}

            <div>
              <label
                htmlFor="login-email"
                className="mb-2 block font-mono text-[10px] uppercase tracking-[0.16em] text-gray-500"
              >
                邮箱
              </label>
              <Input
                id="login-email"
                type="email"
                value={form.email}
                onChange={value => updateField('email', value)}
                placeholder="you@example.com"
                error={errors.email}
                disabled={submitting}
                autoComplete="email"
              />
            </div>

            <div>
              <label
                htmlFor="login-password"
                className="mb-2 block font-mono text-[10px] uppercase tracking-[0.16em] text-gray-500"
              >
                密码
              </label>
              <Input
                id="login-password"
                type="password"
                value={form.password}
                onChange={value => updateField('password', value)}
                placeholder="请输入密码"
                error={errors.password}
                disabled={submitting}
                autoComplete="current-password"
              />
            </div>

            <div className="flex items-center justify-between">
              <Checkbox
                label="记住我"
                checked={remember}
                onCheckedChange={checked => setRemember(checked === true)}
                disabled={submitting}
              />
              <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-gray-400">
                MVP
              </span>
            </div>

            <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
              {submitting ? '登录中...' : '登录'}
            </Button>
          </form>

          <div className="mt-10 border-t border-gray-300 pt-5">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-gray-500">
                  体验账号
                </p>
                <p className="mt-1 font-mono text-[11px] text-gray-700">
                  {DEMO_ACCOUNT.email} / {DEMO_ACCOUNT.password}
                </p>
              </div>
              <button
                type="button"
                className="link-quiet font-mono text-[10px] uppercase tracking-[0.14em]"
                onClick={prefillDemo}
              >
                填入
              </button>
            </div>
            <p className="mt-4 text-[11px] leading-relaxed text-gray-500">
              账号由管理员创建，MVP 不提供注册与找回密码。
            </p>
          </div>
        </div>
      </main>
    </div>
  )
}
