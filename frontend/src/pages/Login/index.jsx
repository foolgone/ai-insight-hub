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
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-primary-50 to-primary-100 p-4">
      <main className="w-full max-w-[400px] rounded-lg bg-white p-8 shadow-xl">
        <div className="mb-8 text-center">
          <div
            className="mx-auto grid h-16 w-16 place-items-center rounded-lg bg-primary-600 text-xl font-bold text-white"
            aria-hidden="true"
          >
            AI
          </div>
          <h1 className="mt-4 text-2xl font-bold text-gray-900">欢迎使用 AI Insight Hub</h1>
          <p className="mt-1 text-sm text-gray-600">AI 驱动的智能对话数据分析平台</p>
        </div>

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {errors.form ? (
            <div
              role="alert"
              className="rounded border border-error-200 bg-error-50 px-3 py-2 text-sm text-error-700"
            >
              {errors.form}
            </div>
          ) : null}

          <div>
            <label htmlFor="login-email" className="mb-1 block text-sm font-medium text-gray-700">
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
              className="mb-1 block text-sm font-medium text-gray-700"
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
          </div>

          <Button type="submit" fullWidth loading={submitting} disabled={submitting}>
            {submitting ? '登录中...' : '登录'}
          </Button>
        </form>

        <p className="mt-6 text-center text-xs text-gray-500">
          账号由管理员创建，MVP 不提供注册与找回密码
        </p>

        <div className="mt-3 flex items-center justify-between rounded bg-gray-50 px-3 py-2 text-xs text-gray-600">
          <span>
            体验账号：{DEMO_ACCOUNT.email} / {DEMO_ACCOUNT.password}
          </span>
          <button type="button" className="text-primary-600 hover:underline" onClick={prefillDemo}>
            点击预填
          </button>
        </div>
      </main>
    </div>
  )
}
