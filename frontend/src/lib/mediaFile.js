/** 音视频上传的共用常量与判断（上传弹窗、新建数据源抽屉共用）。 */

export const MEDIA_EXTENSIONS = ['.mp3', '.wav', '.m4a', '.mp4', '.mov']

export const MEDIA_ACCEPT = MEDIA_EXTENSIONS.join(',')

export const MEDIA_LABEL = 'MP3 / WAV / M4A / MP4 / MOV'

export const TEXT_ACCEPT = '.csv,.json,.xlsx,.txt'

export const UPLOAD_ACCEPT = `${TEXT_ACCEPT},${MEDIA_ACCEPT}`

export const MAX_UPLOAD_BYTES = 50 * 1024 * 1024

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
