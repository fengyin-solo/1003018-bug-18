<template>
  <section class="page" data-module="rectifier">
    <header class="page-head">
      <div>
        <h2>开关电源管理</h2>
        <p class="page-desc">维护开关电源，围绕电源编号、额定功率、所属站点、整流模块数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记开关电源</button>
        <button class="btn" type="button" @click="openWorkOrder">处理单</button>
        <button class="btn" type="button" @click="exportRows">导出开关电源清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="applyFilters">
      <label class="filter-item">
        <span>电源编号</span>
        <input v-model="keyword" placeholder="按电源编号检索" />
      </label>
      <label class="filter-item">
        <span>电源状态</span>
        <select v-model="statusFilter">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <div v-if="errorMessage" class="error-banner">
      <span>{{ errorMessage }}</span>
      <button class="btn" type="button" @click="refresh">重新加载</button>
    </div>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button class="link" type="button" @click="openDetail(row)">详情</button>
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length && !loading">
          <td :colspan="columns.length + 1" class="empty-state">暂无开关电源数据，可先登记开关电源</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条开关电源记录 · 第 {{ page }} / {{ maxPage }} 页</span>
      <span v-if="noticeMessage" class="error-text">{{ noticeMessage }}</span>
      <span class="pager">
        <button class="btn" type="button" :disabled="page <= 1 || loading" @click="gotoPage(page - 1)">上一页</button>
        <button class="btn" type="button" :disabled="page >= maxPage || loading" @click="gotoPage(page + 1)">下一页</button>
      </span>
    </footer>

    <div v-if="detailRow" class="panel-mask" @click.self="closeDetail">
      <div class="panel">
        <header class="panel-head">
          <strong>{{ panelTitle }}</strong>
          <button class="link" type="button" @click="closeDetail">关闭</button>
        </header>
        <dl class="detail-grid">
          <template v-for="column in columns" :key="column">
            <dt>{{ column }}</dt>
            <dd>{{ detailRow[column] ?? '—' }}</dd>
          </template>
        </dl>
        <form v-if="panelMode !== 'view'" class="panel-form" @submit.prevent="submitPanel">
          <p v-if="panelMode === 'action'" class="panel-hint">
            「{{ panelAction }}」会与下面的运行参数一并落盘，列表与详情同步更新。
          </p>
          <label v-for="field in metricFields" :key="field" class="filter-item">
            <span>{{ field }}</span>
            <input v-model="panelForm[field]" :placeholder="`填写${field}`" />
          </label>
          <div class="panel-actions">
            <button class="btn primary" type="submit">
              {{ panelMode === 'edit' ? '保存参数' : `确认${panelAction}并落盘` }}
            </button>
            <button class="btn ghost" type="button" @click="panelMode = 'view'">返回详情</button>
          </div>
        </form>
        <div v-else class="panel-actions">
          <button class="btn" type="button" @click="startEdit">修改运行参数</button>
        </div>
        <p v-if="panelMessage" class="error-text">{{ panelMessage }}</p>
      </div>
    </div>

    <div v-if="workOpen" class="panel-mask">
      <div class="panel">
        <header class="panel-head">
          <strong>开关电源处理单</strong>
          <button class="link" type="button" @click="closeWorkOrder">关闭</button>
        </header>
        <div v-if="workError" class="error-banner">
          <span>{{ workError }}</span>
          <button class="btn" type="button" @click="loadWorkList">重新拉取</button>
        </div>
        <p v-else-if="workLoading">整流模块清单拉取中…</p>
        <template v-else-if="currentWork">
          <p class="panel-hint">
            第 {{ workIndex + 1 }} / {{ workList.length }} 台 · 已完成 {{ workDoneCount }} 台
            <template v-if="workAllDone">· 全部处理完成</template>
          </p>
          <dl class="detail-grid">
            <dt>电源编号</dt>
            <dd>{{ currentWork.电源编号 ?? '—' }}</dd>
            <dt>所属站点</dt>
            <dd>{{ currentWork.所属站点 ?? '—' }}</dd>
            <dt>电源状态</dt>
            <dd>{{ currentWork.电源状态 ?? '—' }}</dd>
          </dl>
          <form class="panel-form" @submit.prevent="saveWorkUnit">
            <label v-for="field in metricFields" :key="field" class="filter-item">
              <span>{{ field }}</span>
              <input v-model="workForm[field]" :placeholder="`填写${field}`" />
            </label>
            <div class="panel-actions">
              <button class="btn primary" type="submit">保存本台并继续</button>
              <button class="btn ghost" type="button" :disabled="workIndex <= 0" @click="stepWork(-1)">上一台</button>
              <button class="btn ghost" type="button" :disabled="workIndex >= workList.length - 1" @click="stepWork(1)">下一台</button>
            </div>
          </form>
        </template>
        <p v-else>没有待处理的开关电源。</p>
        <p v-if="workMessage" class="error-text">{{ workMessage }}</p>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'

import { fetchJson, request } from '@/api/client'

type Row = Record<string, string | number | null>

interface PagePayload {
  items: Row[]
  total: number
  page: number
  size: number
}

interface ActionPayload {
  ok: boolean
  message: string
  entry?: Row | null
}

const ENDPOINT = '/api/rectifier'
const PAGE_SIZE = 10
const VIEW_STORAGE_KEY = 'rectifier:view'
const WORK_STORAGE_KEY = 'rectifier:workorder'
const columns = ["电源编号", "额定功率", "所属站点", "整流模块数", "负载率", "输出电压", "模块故障", "电源状态"]
const metricFields = ["整流模块数", "负载率", "输出电压", "模块故障"]
const actions = ["记录缺失", "记录异常", "安排更换"]
const statuses = ["正常", "模块缺失", "输出异常", "已更换"]

const rows = ref<Row[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const statusFilter = ref('')
const loading = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const stats = ref([
  { label: '正常电源', value: 0 },
  { label: '异常电源', value: 0 },
  { label: '模块缺失电源', value: 0 },
])

const maxPage = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function errorText(error: unknown, fallback: string): string {
  return error instanceof Error ? error.message : fallback
}

function persistView() {
  localStorage.setItem(VIEW_STORAGE_KEY, JSON.stringify({
    page: page.value,
    keyword: keyword.value,
    status: statusFilter.value,
  }))
}

function restoreView() {
  try {
    const saved = JSON.parse(localStorage.getItem(VIEW_STORAGE_KEY) ?? 'null') as
      | { page?: number; keyword?: string; status?: string }
      | null
    if (saved) {
      page.value = Math.max(1, Number(saved.page) || 1)
      keyword.value = saved.keyword ?? ''
      statusFilter.value = saved.status ?? ''
    }
  } catch {
    // 本地状态损坏时按默认第一页加载
  }
}

async function loadPage() {
  loading.value = true
  errorMessage.value = ''
  noticeMessage.value = ''
  const query = new URLSearchParams({ page: String(page.value), size: String(PAGE_SIZE) })
  if (keyword.value.trim()) query.set('keyword', keyword.value.trim())
  if (statusFilter.value) query.set('status', statusFilter.value)
  try {
    const payload = await fetchJson<PagePayload>(`${ENDPOINT}?${query.toString()}`)
    const max = Math.max(1, Math.ceil((payload.total ?? 0) / PAGE_SIZE))
    if (page.value > max) {
      // 过滤后页数变少：回到最后一页再取一次，条数以服务端 total 为准
      page.value = max
      await loadPage()
      return
    }
    rows.value = payload.items ?? []
    total.value = payload.total ?? 0
    persistView()
    syncDetailFromList()
  } catch (error) {
    // 保留已加载的内容，只说明失败原因，允许原地再取一次
    errorMessage.value = `开关电源列表读取失败：${errorText(error, '接口异常')}，可点击重新加载再取一次`
  } finally {
    loading.value = false
  }
}

async function loadStats() {
  try {
    const summary = await fetchJson<Record<string, number>>(`${ENDPOINT}/stats`)
    stats.value = [
      { label: '正常电源', value: summary['正常'] ?? 0 },
      { label: '异常电源', value: (summary['模块缺失'] ?? 0) + (summary['输出异常'] ?? 0) },
      { label: '模块缺失电源', value: summary['模块缺失'] ?? 0 },
    ]
  } catch {
    // 统计卡片读取失败不打断列表，下次刷新时再取
  }
}

async function refresh() {
  await Promise.all([loadPage(), loadStats()])
}

function applyFilters() {
  page.value = 1
  void loadPage()
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  page.value = 1
  void loadPage()
}

function gotoPage(target: number) {
  if (target < 1 || target > maxPage.value || target === page.value) return
  page.value = target
  void loadPage()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  noticeMessage.value = '开关电源登记入口尚未接入审批流'
}

async function parseResult(response: Response, fallback: string): Promise<ActionPayload> {
  const result = (await response.json()) as ActionPayload & { detail?: string }
  if (!response.ok || !result.ok) {
    throw new Error(result.message || result.detail || fallback)
  }
  return result
}

async function saveEntry(row: Row, values: Record<string, string>): Promise<ActionPayload> {
  const response = await request(`${ENDPOINT}/${row.id}`, {
    method: 'PUT',
    body: JSON.stringify({ values }),
  })
  return parseResult(response, '开关电源参数保存失败')
}

async function postAction(row: Row, values: Record<string, string>): Promise<ActionPayload> {
  const response = await request(`${ENDPOINT}/${row.id}/actions`, {
    method: 'POST',
    body: JSON.stringify({ values }),
  })
  return parseResult(response, '开关电源动作未生效，请稍后重试')
}

const detailRow = ref<Row | null>(null)
const panelMode = ref<'view' | 'edit' | 'action'>('view')
const panelAction = ref('')
const panelForm = ref<Record<string, string>>({})
const panelMessage = ref('')

const panelTitle = computed(() => {
  const row = detailRow.value
  if (!row) return ''
  if (panelMode.value === 'edit') return `修改运行参数 · ${row['电源编号'] ?? ''}`
  if (panelMode.value === 'action') return `${panelAction.value} · ${row['电源编号'] ?? ''}`
  return `开关电源详情 · ${row['电源编号'] ?? ''}`
})

function pickMetrics(row: Row): Record<string, string> {
  const form: Record<string, string> = {}
  for (const field of metricFields) {
    const value = row[field]
    form[field] = value === null || value === undefined ? '' : String(value)
  }
  return form
}

function openDetail(row: Row) {
  detailRow.value = row
  panelMode.value = 'view'
  panelMessage.value = ''
}

function closeDetail() {
  detailRow.value = null
  panelMessage.value = ''
}

function startEdit() {
  if (!detailRow.value) return
  panelForm.value = pickMetrics(detailRow.value)
  panelMode.value = 'edit'
  panelMessage.value = ''
}

function runAction(action: string, row: Row) {
  if (action === '安排更换') {
    void replaceEntry(row)
    return
  }
  // 记录缺失、记录异常：整流模块数等运行参数随动作一并落盘
  detailRow.value = row
  panelAction.value = action
  panelForm.value = pickMetrics(row)
  panelMode.value = 'action'
  panelMessage.value = ''
}

async function replaceEntry(row: Row) {
  errorMessage.value = ''
  try {
    await postAction(row, { action: '安排更换' })
    await refresh()
  } catch (error) {
    errorMessage.value = errorText(error, '开关电源操作失败')
  }
}

async function submitPanel() {
  const row = detailRow.value
  if (!row) return
  panelMessage.value = ''
  try {
    const result = panelMode.value === 'edit'
      ? await saveEntry(row, panelForm.value)
      : await postAction(row, { action: panelAction.value, ...panelForm.value })
    if (result.entry) detailRow.value = result.entry
    panelMode.value = 'view'
    await refresh()
  } catch (error) {
    panelMessage.value = errorText(error, '开关电源操作失败')
  }
}

function syncDetailFromList() {
  // 详情与列表同源：列表刷新后，打开中的详情跟着换成同一份数据
  const current = detailRow.value
  if (!current || panelMode.value !== 'view') return
  const fresh = rows.value.find((row) => Number(row.id) === Number(current.id))
  if (fresh) detailRow.value = fresh
}

const workOpen = ref(false)
const workList = ref<Row[]>([])
const workIndex = ref(0)
const workForm = ref<Record<string, string>>({})
const workDone = ref<number[]>([])
const workDrafts = ref<Record<string, Record<string, string>>>({})
const workLoading = ref(false)
const workError = ref('')
const workMessage = ref('')

const currentWork = computed<Row | null>(() => workList.value[workIndex.value] ?? null)
const workDoneCount = computed(() => workDone.value.length)
const workAllDone = computed(() => workList.value.length > 0 && workDone.value.length >= workList.value.length)

function openWorkOrder() {
  workOpen.value = true
  workMessage.value = ''
  void loadWorkList()
}

function closeWorkOrder() {
  workOpen.value = false
  persistWorkProgress()
  void refresh()
}

async function loadWorkList() {
  workLoading.value = true
  workError.value = ''
  try {
    const payload = await fetchJson<PagePayload>(`${ENDPOINT}?page=1&size=200`)
    workList.value = payload.items ?? []
    restoreWorkProgress()
  } catch (error) {
    // 清单拉不到时说明缺什么，并允许原地重试，不留空白页
    workError.value = `整流模块清单拉取失败：${errorText(error, '接口异常')}，处理单暂时无法展开`
  } finally {
    workLoading.value = false
  }
}

function restoreWorkProgress() {
  let done: number[] = []
  let drafts: Record<string, Record<string, string>> = {}
  try {
    const saved = JSON.parse(localStorage.getItem(WORK_STORAGE_KEY) ?? 'null') as
      | { done?: number[]; drafts?: Record<string, Record<string, string>> }
      | null
    if (saved) {
      done = Array.isArray(saved.done) ? saved.done : []
      drafts = saved.drafts ?? {}
    }
  } catch {
    // 进度损坏时从头开始处理
  }
  const known = new Set(workList.value.map((row) => Number(row.id)))
  workDone.value = done.filter((id) => known.has(id))
  workDrafts.value = drafts
  // 断点续做：落在第一台还没填完的开关电源上
  const next = workList.value.findIndex((row) => !workDone.value.includes(Number(row.id)))
  workIndex.value = next === -1 ? 0 : next
  loadWorkForm()
}

function persistWorkProgress() {
  localStorage.setItem(WORK_STORAGE_KEY, JSON.stringify({
    done: workDone.value,
    drafts: workDrafts.value,
  }))
}

function loadWorkForm() {
  const unit = currentWork.value
  if (!unit) {
    workForm.value = {}
    return
  }
  // 已保存过的内容以服务端为准；填到一半的内容从本地草稿恢复，不被覆盖
  const draft = workDrafts.value[String(unit.id)]
  workForm.value = draft ? { ...draft } : pickMetrics(unit)
}

watch(workForm, (form) => {
  const unit = currentWork.value
  if (!unit || !workOpen.value) return
  workDrafts.value = { ...workDrafts.value, [String(unit.id)]: { ...form } }
  persistWorkProgress()
}, { deep: true })

async function saveWorkUnit() {
  const unit = currentWork.value
  if (!unit) return
  workMessage.value = ''
  try {
    const result = await saveEntry(unit, workForm.value)
    const fresh = result.entry
    if (fresh) {
      workList.value = workList.value.map((row) => (Number(row.id) === Number(unit.id) ? fresh : row))
    }
    const id = Number(unit.id)
    if (!workDone.value.includes(id)) workDone.value = [...workDone.value, id]
    const drafts = { ...workDrafts.value }
    delete drafts[String(id)]
    workDrafts.value = drafts
    persistWorkProgress()
    advanceWork()
  } catch (error) {
    workMessage.value = errorText(error, '保存失败，请重试')
  }
}

function advanceWork() {
  const count = workList.value.length
  for (let step = 1; step <= count; step += 1) {
    const index = (workIndex.value + step) % count
    if (!workDone.value.includes(Number(workList.value[index].id))) {
      workIndex.value = index
      loadWorkForm()
      return
    }
  }
  loadWorkForm()
}

function stepWork(direction: number) {
  const target = workIndex.value + direction
  if (target < 0 || target >= workList.value.length) return
  workIndex.value = target
  loadWorkForm()
}

onMounted(() => {
  restoreView()
  void refresh()
})
</script>

<style scoped>
.error-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  background: #fef3f2;
  border: 1px solid #fecdca;
  color: #b42318;
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  font-size: 13px;
}
.pager { display: inline-flex; gap: 6px; }
.pager .btn:disabled { opacity: 0.5; cursor: not-allowed; }
.panel-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 48px 16px;
  z-index: 10;
}
.panel {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px 20px;
  width: 520px;
  max-width: 100%;
  max-height: 80vh;
  overflow: auto;
}
.panel-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.detail-grid {
  display: grid;
  grid-template-columns: 96px 1fr;
  gap: 6px 12px;
  margin: 0 0 12px;
  font-size: 13px;
}
.detail-grid dt { color: var(--muted); }
.detail-grid dd { margin: 0; }
.panel-form { display: flex; flex-direction: column; gap: 10px; }
.panel-form input,
.filter-item select {
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
}
.panel-actions { display: flex; gap: 8px; margin-top: 4px; }
.panel-hint { color: var(--muted); font-size: 12px; margin: 0 0 4px; }
</style>
