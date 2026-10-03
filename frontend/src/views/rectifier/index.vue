<template>
  <section class="page" data-module="rectifier">
    <header class="page-head">
      <div>
        <h2>开关电源管理</h2>
        <p class="page-desc">维护开关电源，围绕电源编号、额定功率、所属站点、整流模块数做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记开关电源</button>
        <button class="btn" type="button" @click="toggleWorkorder">
          {{ mode === 'workorder' ? '返回电源列表' : '打开处理单' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出开关电源清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <template v-if="mode === 'list'">
      <form class="filter-bar" @submit.prevent="applyFilters">
        <label class="filter-item">
          <span>电源编号</span>
          <input v-model="filters.keyword" placeholder="按电源编号检索" />
        </label>
        <label class="filter-item">
          <span>电源状态</span>
          <select v-model="filters.status">
            <option value="">全部状态</option>
            <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>可执行动作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="row.id" class="row-clickable" @click="void openDetail(row.id)">
            <td v-for="column in columns" :key="column">{{ cell(row, column) }}</td>
            <td class="row-actions" @click.stop>
              <button
                v-for="action in actions"
                :key="action"
                class="link"
                type="button"
                @click="openAction(action, row)"
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
        <span>共 {{ total }} 条开关电源记录 · 第 {{ page }} / {{ pageCount }} 页</span>
        <span class="pager">
          <button class="btn" type="button" :disabled="page <= 1 || loading" @click="gotoPage(page - 1)">上一页</button>
          <button class="btn" type="button" :disabled="page >= pageCount || loading" @click="gotoPage(page + 1)">下一页</button>
        </span>
        <span v-if="errorMessage" class="error-text">
          {{ errorMessage }}
          <button class="link" type="button" @click="void reload()">重新拉取</button>
        </span>
      </footer>

      <aside v-if="detail" class="detail-panel">
        <header class="detail-head">
          <strong>开关电源详情 · {{ detail.电源编号 }}</strong>
          <button class="link" type="button" @click="closeDetail">收起</button>
        </header>
        <dl class="detail-grid">
          <div><dt>所属站点</dt><dd>{{ detail.所属站点 }}</dd></div>
          <div><dt>额定功率</dt><dd>{{ detail.额定功率 }}</dd></div>
          <div><dt>整流模块数</dt><dd>{{ detail.整流模块数 }}</dd></div>
          <div><dt>模块故障</dt><dd>{{ detail.模块故障 }}</dd></div>
          <div><dt>负载功率</dt><dd>{{ detail.负载功率 }}W</dd></div>
          <div><dt>负载电流</dt><dd>{{ detail.负载电流 }}</dd></div>
          <div><dt>负载率</dt><dd>{{ detail.负载率 }}</dd></div>
          <div><dt>电源状态</dt><dd>{{ detail.电源状态 }}</dd></div>
        </dl>
        <form class="detail-edit" @submit.prevent="void saveVoltage()">
          <label>
            <span>输出电压（V）</span>
            <input v-model="voltageDraft" type="number" step="0.1" min="40" max="60" />
          </label>
          <button class="btn primary" type="submit" :disabled="saving">保存输出电压</button>
          <span v-if="detailMessage" class="error-text">{{ detailMessage }}</span>
        </form>
      </aside>
    </template>

    <section v-else class="workorder">
      <div v-if="workorderError" class="error-box">
        <p>{{ workorderError }}</p>
        <button class="btn" type="button" @click="void loadWorkorder()">重新拉取</button>
      </div>
      <p v-else-if="workorderLoading" class="empty-state">整流模块清单拉取中…</p>
      <p v-else-if="!workorderItems.length" class="empty-state">当前没有待处理的开关电源</p>
      <template v-else>
        <p class="page-desc">
          待处理 {{ workorderItems.length }} 台 · 已填报 {{ filledCount }} 台
          <span v-if="filledCount === workorderItems.length">· 处理单已全部填报</span>
        </p>
        <div class="workorder-body">
          <ol class="unit-steps">
            <li
              v-for="(item, index) in workorderItems"
              :key="item.id"
              :class="{ active: index === unitIndex, done: item.已填报 }"
            >
              <button class="link" type="button" @click="selectUnit(index)">
                {{ item.电源编号 }}<template v-if="item.已填报"> ✓</template>
              </button>
            </li>
          </ol>
          <form v-if="currentUnit" class="unit-form" @submit.prevent="void saveUnit()">
            <h3>第 {{ unitIndex + 1 }} / {{ workorderItems.length }} 台 · {{ currentUnit.电源编号 }}</h3>
            <p class="unit-meta">
              {{ currentUnit.所属站点 }} · {{ currentUnit.电源状态 }} ·
              整流模块数 {{ currentUnit.整流模块数 }} · 负载率 {{ currentUnit.负载率 }}
            </p>
            <label>
              <span>处理措施</span>
              <select v-model="unitForm.处理措施">
                <option value="">请选择</option>
                <option v-for="option in measureOptions" :key="option" :value="option">{{ option }}</option>
              </select>
            </label>
            <label>
              <span>处理人</span>
              <input v-model="unitForm.处理人" placeholder="填处理人姓名" />
            </label>
            <label>
              <span>计划完成时间</span>
              <input v-model="unitForm.计划完成时间" type="date" />
            </label>
            <label>
              <span>备注</span>
              <input v-model="unitForm.备注" placeholder="可留空" />
            </label>
            <div class="unit-actions">
              <button class="btn primary" type="submit" :disabled="unitSaving">
                {{ unitSaving ? '保存中…' : '保存并继续下一台' }}
              </button>
              <span v-if="unitMessage" class="error-text">{{ unitMessage }}</span>
            </div>
          </form>
        </div>
      </template>
    </section>

    <div v-if="actionDialog" class="dialog-mask" @click.self="closeAction">
      <div class="dialog">
        <h3>{{ actionDialog.action }} · {{ actionDialog.row.电源编号 }}</h3>
        <label v-if="actionDialog.action === '记录缺失'">
          <span>缺失模块数（在架 {{ actionDialog.row.整流模块数 }} 块）</span>
          <input v-model="actionDialog.value" type="number" min="1" :max="actionDialog.row.整流模块数" />
        </label>
        <label v-else-if="actionDialog.action === '记录异常'">
          <span>实测输出电压（V）</span>
          <input v-model="actionDialog.value" type="number" step="0.1" min="40" max="60" />
        </label>
        <p v-else>确认对 {{ actionDialog.row.电源编号 }} 执行「{{ actionDialog.action }}」？</p>
        <p v-if="actionDialog.error" class="error-text">{{ actionDialog.error }}</p>
        <footer class="dialog-actions">
          <button class="btn primary" type="button" :disabled="actionDialog.busy" @click="void submitAction()">
            {{ actionDialog.busy ? '提交中…' : '确认' }}
          </button>
          <button class="btn ghost" type="button" @click="closeAction">取消</button>
        </footer>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  fetchSummary,
  fetchWorkorder,
  getRectifier,
  listRectifiers,
  runRectifierAction,
  saveWorkorderUnit,
  updateRectifier,
  type RectifierEntry,
} from '@/api/rectifier'

const ENDPOINT = '/api/rectifier'
const PAGE_SIZE = 5
const columns = ["电源编号", "额定功率", "所属站点", "整流模块数", "负载率", "输出电压", "模块故障", "电源状态"]
const actions = ["记录缺失", "记录异常", "安排更换"]
const statuses = ["正常", "模块缺失", "输出异常", "已更换"]
const measureOptions = ["补装整流模块", "均充调整", "更换整机", "现场核查"]

const mode = ref<'list' | 'workorder'>('list')
const rows = ref<RectifierEntry[]>([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const errorMessage = ref('')
const filters = ref({ keyword: '', status: '' })
const stats = ref([{ label: '正常电源', value: 0 }, { label: '模块缺失电源', value: 0 }, { label: '异常电源', value: 0 }])

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

function cell(row: RectifierEntry, column: string) {
  const value = (row as unknown as Record<string, unknown>)[column]
  return value ?? '—'
}

async function reload() {
  loading.value = true
  errorMessage.value = ''
  try {
    const payload = await listRectifiers({
      keyword: filters.value.keyword.trim(),
      status: filters.value.status,
      page: page.value,
      size: PAGE_SIZE,
    })
    if (!payload.items.length && payload.total > 0 && page.value > 1) {
      // 当前页被掏空时退回一页再取，别停在半截空白页
      page.value -= 1
      return await reload()
    }
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '开关电源列表读取失败'
  } finally {
    loading.value = false
  }
}

async function loadSummary() {
  try {
    const summary = await fetchSummary()
    stats.value = [
      { label: '正常电源', value: summary['正常'] ?? 0 },
      { label: '模块缺失电源', value: summary['模块缺失'] ?? 0 },
      { label: '异常电源', value: summary['输出异常'] ?? 0 },
    ]
  } catch {
    // 统计卡拉不到不挡列表，列表自己有错误提示
  }
}

function gotoPage(target: number) {
  page.value = target
  void reload()
}

function applyFilters() {
  page.value = 1
  void reload()
}

function resetFilters() {
  filters.value = { keyword: '', status: '' }
  page.value = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  errorMessage.value = '开关电源登记入口尚未接入审批流'
}

/* 详情：和列表同一个出数口，负载率两边一致 */
const detail = ref<RectifierEntry | null>(null)
const voltageDraft = ref('')
const saving = ref(false)
const detailMessage = ref('')

async function openDetail(id: number) {
  detailMessage.value = ''
  try {
    detail.value = await getRectifier(id)
    voltageDraft.value = String(detail.value.输出电压)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '开关电源详情读取失败'
  }
}

function closeDetail() {
  detail.value = null
}

async function saveVoltage() {
  if (!detail.value) return
  saving.value = true
  detailMessage.value = ''
  try {
    const result = await updateRectifier(detail.value.id, { 输出电压: Number(voltageDraft.value) })
    if (!result.ok || !result.entry) {
      detailMessage.value = result.message
      return
    }
    detail.value = result.entry
    await reload()
  } catch (error) {
    detailMessage.value = error instanceof Error ? error.message : '输出电压保存失败'
  } finally {
    saving.value = false
  }
}

/* 动作：记录缺失、记录异常要带业务字段，和状态一起落盘 */
const actionDialog = ref<{
  action: string
  row: RectifierEntry
  value: string
  error: string
  busy: boolean
} | null>(null)

function openAction(action: string, row: RectifierEntry) {
  actionDialog.value = {
    action,
    row,
    value: action === '记录缺失' ? '1' : action === '记录异常' ? String(row.输出电压) : '',
    error: '',
    busy: false,
  }
}

function closeAction() {
  actionDialog.value = null
}

async function submitAction() {
  const dialog = actionDialog.value
  if (!dialog) return
  dialog.busy = true
  dialog.error = ''
  const values: Record<string, unknown> = { action: dialog.action }
  if (dialog.action === '记录缺失') values['缺失模块数'] = Number(dialog.value)
  if (dialog.action === '记录异常') values['输出电压'] = Number(dialog.value)
  try {
    const result = await runRectifierAction(dialog.row.id, values)
    if (!result.ok) {
      dialog.error = result.message
      return
    }
    if (detail.value?.id === dialog.row.id && result.entry) {
      detail.value = result.entry
    }
    actionDialog.value = null
    await Promise.all([reload(), loadSummary()])
  } catch (error) {
    dialog.error = error instanceof Error ? error.message : '开关电源操作失败'
  } finally {
    dialog.busy = false
  }
}

/* 处理单：断了接着从没填完的那台往下做，填过的内容不被覆盖 */
const workorderItems = ref<RectifierEntry[]>([])
const workorderLoading = ref(false)
const workorderError = ref('')
const unitIndex = ref(0)
const unitForm = ref({ 处理措施: '', 处理人: '', 计划完成时间: '', 备注: '' })
const unitSaving = ref(false)
const unitMessage = ref('')

const currentUnit = computed(() => workorderItems.value[unitIndex.value] ?? null)
const filledCount = computed(() => workorderItems.value.filter((item) => item.已填报).length)

function toggleWorkorder() {
  if (mode.value === 'workorder') {
    mode.value = 'list'
    return
  }
  mode.value = 'workorder'
  void loadWorkorder()
}

async function loadWorkorder() {
  workorderLoading.value = true
  workorderError.value = ''
  try {
    const payload = await fetchWorkorder()
    workorderItems.value = payload.items
    const resume = payload.next_id == null ? 0 : payload.items.findIndex((item) => item.id === payload.next_id)
    selectUnit(resume < 0 ? 0 : resume)
  } catch (error) {
    workorderError.value = `整流模块清单拉取失败：${error instanceof Error ? error.message : '未知原因'}，请重新拉取`
  } finally {
    workorderLoading.value = false
  }
}

function selectUnit(index: number) {
  unitIndex.value = index
  unitMessage.value = ''
  const draft = workorderItems.value[index]?.处理单 ?? {}
  unitForm.value = {
    处理措施: draft['处理措施'] ?? '',
    处理人: draft['处理人'] ?? '',
    计划完成时间: draft['计划完成时间'] ?? '',
    备注: draft['备注'] ?? '',
  }
}

async function saveUnit() {
  const unit = currentUnit.value
  if (!unit) return
  unitSaving.value = true
  unitMessage.value = ''
  try {
    const result = await saveWorkorderUnit(unit.id, { ...unitForm.value })
    if (!result.ok || !result.entry) {
      unitMessage.value = result.message
      return
    }
    // 只更新刚保存的这一台，其他台已填的内容原样保留
    workorderItems.value = workorderItems.value.map((item) => (item.id === unit.id ? result.entry! : item))
    const next = workorderItems.value.findIndex((item) => !item.已填报)
    if (next >= 0) {
      selectUnit(next)
    } else {
      selectUnit(unitIndex.value)
      unitMessage.value = '处理单已全部填报'
    }
  } catch (error) {
    unitMessage.value = error instanceof Error ? error.message : '处理单保存失败'
  } finally {
    unitSaving.value = false
  }
}

onMounted(() => {
  void reload()
  void loadSummary()
})
</script>
