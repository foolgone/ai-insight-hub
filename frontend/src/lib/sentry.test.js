import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const sentryMock = vi.hoisted(() => ({
  init: vi.fn(),
  captureException: vi.fn(),
}))

vi.mock('@sentry/react', () => sentryMock)

describe('lib/sentry', () => {
  beforeEach(() => {
    vi.resetModules()
    sentryMock.init.mockClear()
    sentryMock.captureException.mockClear()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('未配置 DSN 时完全 no-op', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', '')
    const { initSentry, captureException } = await import('./sentry')

    expect(await initSentry()).toBe(false)
    captureException(new Error('boom'))

    expect(sentryMock.init).not.toHaveBeenCalled()
    expect(sentryMock.captureException).not.toHaveBeenCalled()
  })

  it('配置 DSN 后初始化并上报带上下文', async () => {
    vi.stubEnv('VITE_SENTRY_DSN', 'https://example.invalid/1')
    vi.stubEnv('VITE_ENVIRONMENT', 'test')
    const { initSentry, captureException } = await import('./sentry')

    expect(await initSentry()).toBe(true)
    expect(sentryMock.init).toHaveBeenCalledWith(
      expect.objectContaining({
        dsn: 'https://example.invalid/1',
        environment: 'test',
        tracesSampleRate: 0,
      })
    )

    const error = new Error('boom')
    captureException(error, { componentStack: 'stack' })

    expect(sentryMock.captureException).toHaveBeenCalledWith(error, {
      extra: { componentStack: 'stack' },
    })
  })
})
