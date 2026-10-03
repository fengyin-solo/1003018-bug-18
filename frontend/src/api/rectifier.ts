/** 开关电源统一取数口：列表、详情、处理单都从这里走，页面不再各拉各的。 */
import { fetchJson, request } from '@/api/client'

export interface RectifierEntry {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  已填报: boolean
  电源编号: string
  额定功率: string
  所属站点: string
  整流模块数: number
  负载功率: number
  负载电流: string
  负载率: string
  输出电压: number
  模块故障: number
  电源状态: string
  处理单: Record<string, string>
}

export interface PageResult<T> {
  items: T[]
  total: number
  page: number
  size: number
}

export interface ActionResult {
  ok: boolean
  message: string
  entry: RectifierEntry | null
}

export interface WorkorderResult {
  items: RectifierEntry[]
  total: number
  next_id: number | null
}

const ENDPOINT = '/api/rectifier'
/** 读取类请求失败自动再取两次；写操作不重试，避免重复落盘。 */
const RETRY = { retries: 2 }

export function listRectifiers(params: { keyword?: string; status?: string; page: number; size: number }) {
  const query = new URLSearchParams()
  if (params.keyword) query.set('keyword', params.keyword)
  if (params.status) query.set('status', params.status)
  query.set('page', String(params.page))
  query.set('size', String(params.size))
  return fetchJson<PageResult<RectifierEntry>>(`${ENDPOINT}?${query}`, RETRY)
}

export function getRectifier(id: number) {
  return fetchJson<RectifierEntry>(`${ENDPOINT}/${id}`, RETRY)
}

export function fetchSummary() {
  return fetchJson<Record<string, number>>(`${ENDPOINT}/summary`, RETRY)
}

export function fetchWorkorder() {
  return fetchJson<WorkorderResult>(`${ENDPOINT}/workorder`, RETRY)
}

async function send<T>(path: string, method: string, values: Record<string, unknown>): Promise<T> {
  const response = await request(path, { method, body: JSON.stringify({ values }) })
  return (await response.json()) as T
}

export function updateRectifier(id: number, values: Record<string, unknown>) {
  return send<ActionResult>(`${ENDPOINT}/${id}`, 'PUT', values)
}

export function runRectifierAction(id: number, values: Record<string, unknown>) {
  return send<ActionResult>(`${ENDPOINT}/${id}/actions`, 'POST', values)
}

export function saveWorkorderUnit(id: number, values: Record<string, unknown>) {
  return send<ActionResult>(`${ENDPOINT}/workorder/${id}`, 'PUT', values)
}
