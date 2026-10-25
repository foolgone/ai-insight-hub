import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { useMediaQuery } from './useMediaQuery'

const ORIGINAL_MATCH_MEDIA = window.matchMedia

afterEach(() => {
  window.matchMedia = ORIGINAL_MATCH_MEDIA
})

describe('useMediaQuery', () => {
  it('订阅媒体查询并响应 change 事件', () => {
    let listener = null
    const media = {
      matches: true,
      media: '(max-width: 767px)',
      addEventListener: (_event, callback) => {
        listener = callback
      },
      removeEventListener: vi.fn(),
    }
    window.matchMedia = vi.fn().mockReturnValue(media)

    const { result } = renderHook(() => useMediaQuery('(max-width: 767px)'))
    expect(result.current).toBe(true)

    act(() => listener({ matches: false }))
    expect(result.current).toBe(false)
  })

  it('兼容仅支持 addListener 的旧实现', () => {
    const addListener = vi.fn()
    const removeListener = vi.fn()
    window.matchMedia = vi.fn().mockReturnValue({
      matches: false,
      media: '(max-width: 767px)',
      addListener,
      removeListener,
    })

    const { unmount } = renderHook(() => useMediaQuery('(max-width: 767px)'))

    expect(addListener).toHaveBeenCalledTimes(1)
    unmount()
    expect(removeListener).toHaveBeenCalledTimes(1)
  })
})
