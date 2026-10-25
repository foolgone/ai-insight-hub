import { useEffect, useState } from 'react'

/**
 * 订阅一个 CSS 媒体查询（04 §11 Q1）。
 * @param {string} query 媒体查询字符串，如 '(max-width: 767px)'
 * @returns {boolean} 当前是否匹配
 */
export function useMediaQuery(query) {
  const getMatches = () =>
    typeof window === 'undefined' ? false : window.matchMedia(query).matches

  const [matches, setMatches] = useState(getMatches)

  useEffect(() => {
    const media = window.matchMedia(query)
    const listener = event => setMatches(event.matches)

    setMatches(media.matches)
    if (media.addEventListener) media.addEventListener('change', listener)
    else if (media.addListener) media.addListener(listener)

    return () => {
      if (media.removeEventListener) media.removeEventListener('change', listener)
      else if (media.removeListener) media.removeListener(listener)
    }
  }, [query])

  return matches
}
