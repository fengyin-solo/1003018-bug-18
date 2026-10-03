/** 统一请求封装：拼后端地址、抛网络错误、给页脚留一句可读的说明。 */
const API_BASE = import.meta.env.VITE_API_BASE ?? ''

export function request(path: string, init?: RequestInit): Promise<Response> {
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  return fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  }).catch((error: unknown) => {
    const detail = error instanceof Error ? error.message : '请求未送达'
    throw new Error(`接口请求失败：${detail}`)
  })
}

type FetchOptions = {
  /** 网络层失败时的重试次数：数据拉不到就再取，别停在半截。 */
  retries?: number
}

export async function fetchJson<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { retries = 0 } = options
  let lastError: Error = new Error('数据读取失败')
  for (let attempt = 0; attempt <= retries; attempt += 1) {
    try {
      const response = await request(path)
      if (!response.ok) {
        throw new Error(`接口返回 ${response.status}，数据未更新`)
      }
      return (await response.json()) as T
    } catch (error) {
      lastError = error instanceof Error ? error : new Error('数据读取失败')
      if (attempt < retries) {
        await new Promise((resolve) => setTimeout(resolve, 300 * (attempt + 1)))
      }
    }
  }
  throw lastError
}
