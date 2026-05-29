/** 生成会话 ID。局域网 HTTP（如 192.168.x.x）不是安全上下文，crypto.randomUUID() 会抛错导致白屏。 */
export function createSessionId(): string {
  if (globalThis.isSecureContext && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (ch) => {
    const r = (Math.random() * 16) | 0
    const v = ch === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
