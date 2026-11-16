<template>
  <div class="knowledge-library">
    <header class="knowledge-heading">
      <div>
        <h1>资料库</h1>
        <p>
          管理 AI 解析与追问使用的教学资料，引用可追溯到课件页码或原文段落。
        </p>
      </div>
      <el-button type="primary" :icon="Upload" @click="uploadOpen = true"
        >上传资料</el-button
      >
    </header>
    <div class="knowledge-toolbar">
      <el-input
        v-model="query"
        clearable
        :prefix-icon="Search"
        aria-label="搜索资料"
        placeholder="搜索资料名称、文件名或说明"
      />
      <el-select v-model="filter" aria-label="筛选资料状态">
        <el-option label="全部资料" value="all" /><el-option
          label="AI 可用"
          value="enabled"
        /><el-option label="已停用 / 待补充" value="disabled" />
      </el-select>
      <span
        >{{ documents.length }} 份资料 ·
        {{
          documents.filter((d) => d.enabled && d.status === 'ready').length
        }}
        份供 AI 使用</span
      >
      <el-button :icon="Refresh" :disabled="loading || saving" @click="refresh"
        >刷新</el-button
      >
    </div>
    <div v-if="initialError" class="knowledge-empty" role="alert">
      <p>资料库加载失败，请重试。</p>
      <el-button @click="refresh">重新加载</el-button>
    </div>
    <div
      v-else-if="!documents.length && !initialLoading"
      class="knowledge-empty"
    >
      <el-icon :size="36"><FolderOpened /></el-icon>
      <h2>添加第一份教学资料</h2>
      <p>课件、教材摘录和教师整理的文字说明都可以作为 AI 解释的依据。</p>
      <el-button type="primary" @click="uploadOpen = true">上传资料</el-button>
    </div>
    <div v-else class="knowledge-workspace" v-loading="initialLoading">
      <aside class="knowledge-list" aria-label="资料列表">
        <p v-if="!filtered.length" class="knowledge-no-match">
          没有匹配的资料，试试其他关键词。
        </p>
        <button
          v-for="doc in filtered"
          :key="doc.id"
          type="button"
          class="knowledge-row"
          :class="{ selected: selected?.id === doc.id }"
          :aria-pressed="selected?.id === doc.id"
          :disabled="saving"
          @click="choose(doc.id)"
        >
          <span class="knowledge-format">{{ doc.format.toUpperCase() }}</span>
          <span class="knowledge-row-body"
            ><strong>{{ doc.title }}</strong>
            <small
              >{{ doc.page_count }} {{ doc.unit }} ·
              {{ bytes(doc.size) }}</small
            >
            <span
              class="knowledge-state"
              :class="{ active: doc.enabled && doc.status === 'ready' }"
              >{{
                doc.status !== 'ready'
                  ? '文字待补充'
                  : doc.enabled
                    ? 'AI 可用'
                    : '已停用'
              }}</span
            >
          </span>
        </button>
      </aside>
      <section
        class="knowledge-detail"
        v-loading="loading"
        aria-label="资料详情"
      >
        <template v-if="selected">
          <div class="knowledge-detail-top">
            <h2>资料信息</h2>
            <div>
              <el-button
                :icon="Download"
                :disabled="loading || saving"
                @click="download"
                >下载文件</el-button
              >
              <el-button
                type="danger"
                text
                :disabled="loading || saving"
                @click="removeSelected"
                >删除</el-button
              >
            </div>
          </div>
          <p class="knowledge-filename">
            {{ selected.filename }} ·
            {{ selected.text_chars.toLocaleString() }} 字 · 更新于
            {{ date(selected.updated_at) }}
          </p>
          <el-form label-position="top" @submit.prevent="saveSelected">
            <el-form-item label="资料名称"
              ><el-input
                v-model="form.title"
                maxlength="160"
                show-word-limit
                :disabled="saving || loading"
            /></el-form-item>
            <el-form-item label="资料说明"
              ><el-input
                v-model="form.description"
                type="textarea"
                :rows="2"
                maxlength="2000"
                :disabled="saving || loading"
                placeholder="例如：杨扬《车站信号自动控制》课件，用于解释进路、信号及联锁电路。"
            /></el-form-item>
            <div class="knowledge-publish">
              <div>
                <el-switch
                  v-model="form.enabled"
                  aria-label="允许 AI 使用这份资料"
                  :disabled="saving || loading || selected.status !== 'ready'"
                /><span>允许 AI 使用这份资料</span><small>保存后生效</small>
              </div>
              <el-button
                type="primary"
                native-type="submit"
                :loading="saving"
                :disabled="!dirty || loading || !form.title.trim()"
                >保存修改</el-button
              >
            </div>
          </el-form>
          <div class="knowledge-preview-heading">
            <h2>已提取内容</h2>
            <span
              >{{ selected.page_count }} {{ selected.unit }} ·
              {{ selected.sparse_pages }} {{ selected.unit }}文字较少</span
            >
          </div>
          <div class="knowledge-warnings" role="note">
            <p v-for="warning in selected.warnings" :key="warning">
              {{ warning }}
            </p>
          </div>
          <nav
            v-if="selected.page_count"
            class="knowledge-page-control"
            aria-label="预览页码"
          >
            <el-button :disabled="page <= 1" @click="page--"
              >上一{{ selected.unit }}</el-button
            >
            <label
              >第
              <el-input-number
                v-model="page"
                :min="1"
                :max="selected.page_count"
                :precision="0"
                controls-position="right"
                aria-label="预览页码"
              />
              / {{ selected.page_count }} {{ selected.unit }}</label
            >
            <el-button :disabled="page >= selected.page_count" @click="page++"
              >下一{{ selected.unit }}</el-button
            >
          </nav>
          <div
            class="knowledge-page-text"
            tabindex="0"
            aria-label="提取文字预览"
          >
            <p class="knowledge-page-label">
              {{ selected.title }}，{{
                currentPage?.location || '无可检索文字'
              }}
            </p>
            <pre v-if="currentPage?.text">{{ currentPage.text }}</pre>
            <p v-else class="knowledge-no-match">
              这一{{ selected.unit }}没有提取到文字。原图保留在下载文件中，AI
              不会猜测图中内容。
            </p>
          </div>
          <p class="knowledge-footnote">
            AI
            优先结合本题解析与相关资料回答。停用或删除只影响后续检索，已有对话中的引用仍保留。
          </p>
        </template>
      </section>
    </div>

    <el-dialog
      v-model="uploadOpen"
      title="上传教学资料"
      width="min(560px, 94vw)"
      :close-on-click-modal="!uploading"
      :close-on-press-escape="!uploading"
      :show-close="!uploading"
      @closed="resetUpload"
    >
      <el-form label-position="top" @submit.prevent="upload">
        <el-form-item label="资料文件">
          <input
            id="knowledge-file"
            ref="fileInput"
            type="file"
            accept=".pptx,.pdf,.docx,.txt,.md"
            :disabled="uploading"
            @change="pickFile"
          />
          <label class="knowledge-file-label" for="knowledge-file"
            ><el-icon><Upload /></el-icon
            ><strong>{{ uploadFile?.name || '点击选择文件' }}</strong
            ><span
              >PPTX、PDF、DOCX、TXT、Markdown，单份不超过 40 MB</span
            ></label
          >
          <p class="knowledge-upload-hint">
            旧版 .ppt 请先在 PowerPoint 中另存为
            .pptx。扫描件和图片中的文字需先做 OCR。
          </p>
        </el-form-item>
        <el-form-item label="资料名称"
          ><el-input
            v-model="uploadForm.title"
            maxlength="160"
            :disabled="uploading"
            placeholder="留空时使用文件名"
        /></el-form-item>
        <el-form-item label="资料说明"
          ><el-input
            v-model="uploadForm.description"
            type="textarea"
            :rows="2"
            maxlength="2000"
            :disabled="uploading"
        /></el-form-item>
        <el-form-item label="打开密码（可选）"
          ><el-input
            v-model="uploadForm.password"
            type="password"
            autocomplete="new-password"
            maxlength="256"
            :disabled="uploading"
            placeholder="加密文件填写；密码不保存"
        /></el-form-item>
        <el-checkbox v-model="uploadForm.enabled" :disabled="uploading"
          >解析成功后供 AI 使用</el-checkbox
        >
        <p v-if="uploading" class="knowledge-upload-hint" role="status">
          正在上传并提取内容，请稍候…
        </p>
        <div class="knowledge-upload-actions">
          <el-button :disabled="uploading" @click="uploadOpen = false"
            >取消</el-button
          ><el-button
            type="primary"
            native-type="submit"
            :loading="uploading"
            :disabled="!uploadFile"
            >上传并解析</el-button
          >
        </div>
      </el-form>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import {
  Download,
  FolderOpened,
  Refresh,
  Search,
  Upload,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import * as api from '@/api/knowledge'
import { useKnowledgeLibrary } from '@/features/knowledge/useKnowledgeLibrary'
import '@/features/knowledge/knowledge.css'

const state = useKnowledgeLibrary(api)
const {
  documents,
  selected,
  loading,
  saving,
  query,
  filter,
  page,
  form,
  filtered,
  currentPage,
  dirty,
} = state
const initialLoading = ref(true),
  initialError = ref(false),
  uploadOpen = ref(false),
  uploading = ref(false)
const uploadFile = ref(null),
  fileInput = ref(null)
const uploadForm = reactive({
  title: '',
  description: '',
  password: '',
  enabled: true,
})
const bytes = (n) =>
  n < 1024 * 1024
    ? `${Math.ceil(n / 1024)} KB`
    : `${(n / 1024 / 1024).toFixed(1)} MB`
const date = (value) =>
  new Date(
    value.endsWith('Z') || /[+-]\d\d:\d\d$/.test(value) ? value : value + 'Z',
  ).toLocaleString('zh-CN', { hour12: false })
async function confirmDiscard() {
  if (!dirty.value) return true
  try {
    await ElMessageBox.confirm('当前修改尚未保存，是否放弃修改？', '切换资料', {
      confirmButtonText: '放弃修改',
      cancelButtonText: '继续编辑',
      type: 'warning',
    })
    return true
  } catch {
    return false
  }
}
async function choose(id) {
  if (selected.value?.id !== id && (await confirmDiscard())) {
    try {
      await state.select(id)
    } catch {
      /* request shows error; existing form remains */
    }
  }
}
async function refresh() {
  if (!(await confirmDiscard())) return
  initialError.value = false
  try {
    await state.reload()
  } catch {
    initialError.value = true
  } finally {
    initialLoading.value = false
  }
}
async function saveSelected() {
  try {
    await state.save()
    ElMessage.success('资料已更新，后续 AI 回答使用新的设置。')
  } catch (error) {
    if (error.response?.status === 409) await refresh()
  }
}
async function removeSelected() {
  const name = selected.value.title
  try {
    await ElMessageBox.confirm(
      `删除“${name}”后，AI 后续回答不再检索它。已有对话引用保留。此操作不能撤销。`,
      '删除资料',
      {
        confirmButtonText: '删除资料',
        cancelButtonText: '取消',
        type: 'warning',
      },
    )
  } catch {
    return
  }
  try {
    const result = await state.remove()
    ElMessage.success(result.message)
  } catch {
    /* request shows error */
  }
}
async function download() {
  try {
    const blob = await api.downloadMaterial(selected.value.id)
    const url = URL.createObjectURL(blob),
      anchor = document.createElement('a')
    anchor.href = url
    anchor.download = selected.value.filename
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  } catch {
    /* request shows error */
  }
}
function pickFile(event) {
  const file = event.target.files?.[0]
  if (file && file.size > 40 * 1024 * 1024) {
    ElMessage.error('单份资料不能超过 40 MB。')
    event.target.value = ''
    uploadFile.value = null
    return
  }
  uploadFile.value = file || null
}
function resetUpload() {
  uploadFile.value = null
  Object.assign(uploadForm, {
    title: '',
    description: '',
    password: '',
    enabled: true,
  })
  if (fileInput.value) fileInput.value.value = ''
}
async function upload() {
  if (!uploadFile.value || uploading.value || !(await confirmDiscard())) return
  uploading.value = true
  const body = new FormData()
  body.append('file', uploadFile.value)
  for (const [key, value] of Object.entries(uploadForm)) body.append(key, value)
  try {
    const doc = await api.uploadMaterial(body)
    uploadOpen.value = false
    await state.reload(doc.id)
    ElMessage.success(
      doc.status === 'ready'
        ? '资料已上传，可以查看提取内容。'
        : '文件已保存，请补充可检索文字。',
    )
  } catch {
    /* retain file/metadata for correction; never retain password */
  } finally {
    uploading.value = false
    uploadForm.password = ''
  }
}
onMounted(refresh)
</script>
