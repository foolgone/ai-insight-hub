/** 上传相关的共用常量与判断（上传弹窗、新建数据源抽屉共用）。 */

/** 单文件大小上限（MB）：与后端 MAX_UPLOAD_SIZE_MB、nginx client_max_body_size 对齐。 */
export const MAX_UPLOAD_MB = 100

export const MAX_UPLOAD_BYTES = MAX_UPLOAD_MB * 1024 * 1024

/** 文案用（如「单文件 ≤ 100MB」）。 */
export const MAX_UPLOAD_LABEL = `${MAX_UPLOAD_MB}MB`

export const MEDIA_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.mp4', '.mov']

export const MEDIA_ACCEPT = MEDIA_EXTENSIONS.join(',')

export const MEDIA_LABEL = 'MP3 / WAV / M4A / MP4 / MOV'

export const TEXT_ACCEPT = '.csv,.json,.xlsx,.txt'

export const UPLOAD_ACCEPT = `${TEXT_ACCEPT},${MEDIA_ACCEPT}`

/**
 * 是否为音视频文件（按扩展名判断，与后端 MEDIA_UPLOAD_EXTENSIONS 对齐）。
 * @param {File|null|undefined} file
 * @returns {boolean}
 */
export function isMediaFile(file) {
  if (!file) return false
  const name = String(file.name || '').toLowerCase()
  return MEDIA_EXTENSIONS.some(ext => name.endsWith(ext))
}
