import { Toaster } from 'react-hot-toast'

/**
 * 全局 Toaster（在 main.jsx 挂载一次）。
 */
export function ToastContainer() {
  return (
    <Toaster
      position="top-right"
      containerStyle={{ top: 24, right: 24 }}
      toastOptions={{
        duration: 3000,
        style: {
          fontSize: '14px',
          maxWidth: '320px',
        },
      }}
    />
  )
}
