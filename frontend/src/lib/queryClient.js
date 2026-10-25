import { QueryClient } from '@tanstack/react-query'

/**
 * 创建 React Query 客户端（R-4 默认值）。
 * @returns {QueryClient}
 */
export function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30 * 1000,
        gcTime: 5 * 60 * 1000,
        retry: (failureCount, error) => {
          // 401/403 不重试，交拦截器处理
          if (error && (error.status === 401 || error.status === 403)) return false
          return failureCount < 1
        },
        refetchOnWindowFocus: false,
      },
    },
  })
}

export const queryClient = createQueryClient()
