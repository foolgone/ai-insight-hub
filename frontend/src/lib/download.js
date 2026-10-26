/**
 * 生成 CSV 文本（字段加引号并转义内部引号）。
 *
 * 文本以 UTF-8 BOM（U+FEFF）开头：Excel 在无 BOM 时按系统 ANSI 代码页
 * （简体中文 Windows 为 GBK）解码 .csv，中文会显示为乱码；BOM 用于声明
 * 该文件是 UTF-8。后端解析器以 utf-8-sig 优先解码，可原样回传导入。
 *
 * @param {Array<Array<string|number|null|undefined>>} rows
 * @returns {string}
 */
export function toCsv(rows) {
  return (
    '\uFEFF' +
    rows
      .map(row => row.map(cell => `"${String(cell ?? '').replace(/"/g, '""')}"`).join(','))
      .join('\r\n')
  )
}

/**
 * 触发浏览器下载 Blob。
 * @param {string} filename
 * @param {Blob} blob
 */
export function downloadBlobFile(filename, blob) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
}

/**
 * 触发浏览器下载文本文件。
 * @param {string} filename
 * @param {string} content
 * @param {string} [mime]
 */
export function downloadTextFile(filename, content, mime = 'text/csv;charset=utf-8') {
  downloadBlobFile(filename, new Blob([content], { type: mime }))
}
