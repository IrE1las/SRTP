<template>
  <Teleport to="body">
    <button
      v-show="!visible"
      ref="launcher"
      class="tutor-launcher"
      :style="dockStyle"
      :class="{ 'has-unread': unread }"
      aria-controls="chapter-ai-window"
      :aria-expanded="visible"
      :aria-label="unread ? '打开AI解析，有新的回答' : '打开AI解析与追问'"
      @click="openWindow"
    >
      <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
        <path
          d="M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Z"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linejoin="round"
        />
        <path
          d="M7 9h10M7 13h7"
          stroke="currentColor"
          stroke-width="1.6"
          stroke-linecap="round"
        />
      </svg>
      <span>AI解析</span
      ><span class="launcher-detail">{{
        busy ? '回答中' : unread ? '新回答' : '可追问'
      }}</span>
    </button>
    <section
      v-show="visible"
      id="chapter-ai-window"
      ref="panel"
      class="tutor-panel"
      :class="{ 'is-wide': wide, 'is-dragging': dragging }"
      :style="[dockStyle, panelPosition]"
      role="dialog"
      aria-modal="false"
      aria-labelledby="chapter-ai-title"
      aria-describedby="chapter-ai-context"
      :aria-busy="Boolean(state?.sending || state?.generating)"
      tabindex="-1"
      @keydown.esc.stop.prevent="closeWindow"
    >
      <header class="tutor-heading" @pointerdown="startDrag">
        <div>
          <h3 id="chapter-ai-title">AI解析与追问</h3>
          <p>{{ busy ? '正在组织讲解…' : '围绕题目，继续问清楚' }}</p>
        </div>
        <div class="window-actions">
          <button
            class="resize-button"
            :aria-pressed="wide"
            @click="toggleSize"
          >
            {{ wide ? '还原' : '放大' }}
          </button>
          <button
            class="minimize-button"
            aria-label="收起AI窗口"
            title="收起AI窗口"
            @click="closeWindow"
          >
            <span aria-hidden="true">−</span>
          </button>
        </div>
      </header>
      <div id="chapter-ai-context" class="tutor-context">
        <span>{{ questionLabel || '当前题目' }}</span>
        <p>{{ questionLoading ? '正在加载题目…' : questionStem }}</p>
      </div>
      <div
        ref="conversation"
        class="tutor-body"
        role="log"
        aria-label="本题AI对话"
        tabindex="0"
      >
        <p v-if="questionLoading" class="tutor-notice" role="status">
          正在切换本题对话…
        </p>
        <p v-else-if="!attemptId" class="tutor-notice">
          提交本题后，可让AI详细讲解，并继续追问原理与易错点。
        </p>
        <template v-else>
          <p
            v-if="state?.loading && !state?.loaded"
            class="tutor-notice"
            role="status"
          >
            正在加载本题对话…
          </p>
          <div v-if="state?.error" class="tutor-error" role="alert">
            <span>{{ state.error }}</span><button
              :disabled="busy"
              @click="state.pending ? tutor.send() : tutor.load()"
            >
              {{ state.pending ? '重试本轮' : '重新加载' }}
            </button>
          </div>
          <div v-if="state?.loaded && !state.configured" class="tutor-notice">
            AI暂未配置，请联系管理员。<button
              class="text-button"
              @click="tutor.load()"
            >
              重新检查配置
            </button>
          </div>
          <template v-if="state?.loaded && state.configured">
            <div v-if="!state.turns.length" class="tutor-start">
              <span class="start-mark" aria-hidden="true">?</span>
              <h4>这道题，哪里还没弄明白？</h4>
              <p>结合你的作答讲解正确答案、易错点和相关专业知识。</p>
              <button
                class="tutor-primary"
                :disabled="busy || Boolean(state.pending)"
                @click="tutor.send('explain')"
              >
                AI详细解析
              </button>
            </div>
            <article
              v-for="turn in state.turns"
              :key="turn.id"
              class="tutor-turn"
            >
              <div class="student-message">
                <span>{{
                  turn.action === 'explain' ? '本题详细解析' : '我的追问'
                }}</span>
                <p v-if="turn.action !== 'explain'">{{ turn.question }}</p>
              </div>
              <div
                class="assistant-message"
                :class="{ 'is-refused': turn.status === 'refused' }"
              >
                <div class="assistant-label">
                  <strong>AI助教</strong
                  ><span v-if="turn.status === 'refused'">超出讨论范围</span
                  ><span v-else-if="turn.status === 'clarify'"
                    >需要补充说明</span
                  ><span v-else-if="turn.general_knowledge"
                    >含专业知识补充</span
                  >
                </div>
                <p class="assistant-text">{{ turn.answer }}</p>
                <details v-if="turn.sources?.length" class="tutor-sources">
                  <summary>查看参考依据（{{ turn.sources.length }}）</summary>
                  <div v-for="source in turn.sources" :key="source.id">
                    <strong>[{{ source.id }}] {{ source.label }}</strong>
                    <p>{{ source.text }}</p>
                  </div>
                </details>
              </div>
            </article>
            <p v-if="busy" class="tutor-pending" role="status">
              <span class="pending-dot" aria-hidden="true"></span
              >{{
                state.sending
                  ? 'AI正在理解问题并组织讲解…可以收起窗口继续做题。'
                  : '本题有回答正在生成，将自动更新。'
              }}
            </p>
          </template>
        </template>
      </div>
      <footer
        v-if="
          attemptId && state?.loaded && state.configured && state.turns.length
        "
        class="tutor-footer"
      >
        <div class="tutor-suggestions" aria-label="建议追问">
          <button
            v-for="prompt in suggestions"
            :key="prompt"
            :disabled="busy || Boolean(state.pending) || atLimit"
            @click="tutor.send('ask', prompt)"
          >
            {{ prompt }}
          </button>
        </div>
        <form class="tutor-composer" @submit.prevent="tutor.send()">
          <label :for="inputId" class="sr-only">追问题目或相关专业知识</label>
          <textarea
            :id="inputId"
            v-model="state.draft"
            :disabled="busy || Boolean(state.pending) || atLimit"
            rows="2"
            maxlength="1500"
            placeholder="继续追问原理、错因或相关知识…"
            @keydown.ctrl.enter.prevent="tutor.send()"
            @keydown.meta.enter.prevent="tutor.send()"
          ></textarea>
          <div class="composer-actions">
            <span>{{
              atLimit
                ? '本次对话已达20轮，可重新练习后开启新对话。'
                : 'AI讲解供学习核对'
            }}</span><button
              class="tutor-primary"
              type="submit"
              :disabled="
                busy || Boolean(state.pending) || atLimit || !state.draft.trim()
              "
            >
              发送追问
            </button>
          </div>
        </form>
      </footer>
    </section>
  </Teleport>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import request from '@/utils/request'
import { createChapterTutor } from './useChapterTutor.js'
const props = defineProps({
  attemptId: { type: String, default: '' },
  questionLabel: { type: String, default: '' },
  questionStem: { type: String, default: '' },
  questionLoading: Boolean,
  navigationAnchor: { type: Object, default: null },
})
const tutor = createChapterTutor({
  get: (...args) => request.get(...args),
  post: (...args) => request.post(...args),
})
const { state } = tutor
const visible = ref(false),
  wide = ref(false),
  dragging = ref(false)
const launcher = ref(null),
  panel = ref(null),
  conversation = ref(null),
  position = ref(null),
  unreadByAttempt = ref({})
const mobile = ref(window.innerWidth <= 700)
const dockRight = ref(24)
const dockStyle = computed(() => ({
  '--tutor-dock-right': `${dockRight.value}px`,
}))
const inputId = computed(() => `tutor-input-${props.attemptId}`)
const busy = computed(() =>
  Boolean(
    state.value?.sending || state.value?.generating || state.value?.loading,
  ),
)
const unread = computed(() => Boolean(unreadByAttempt.value[props.attemptId]))
const atLimit = computed(
  () => (state.value?.turns.length || 0) >= (state.value?.maxTurns || 20),
)
const suggestions = [
  '用更简单的话解释',
  '为什么我的答案不合适？',
  '给我一个相关例子',
]
const panelPosition = computed(() =>
  position.value && !mobile.value
    ? {
        left: `${position.value.x}px`,
        top: `${position.value.y}px`,
        right: 'auto',
        bottom: 'auto',
      }
    : {},
)
async function scrollToLatest() {
  await nextTick()
  const lastTurn = conversation.value
    ?.querySelectorAll('.tutor-turn')
    .item((state.value?.turns.length || 1) - 1)
  if (conversation.value)
    conversation.value.scrollTop = lastTurn
      ? Math.max(0, lastTurn.offsetTop - 12)
      : 0
}
async function openWindow() {
  visible.value = true
  unreadByAttempt.value[props.attemptId] = false
  await scrollToLatest()
  if (position.value && !mobile.value)
    position.value = clampPosition(position.value.x, position.value.y)
  panel.value?.focus({ preventScroll: true })
}
async function closeWindow() {
  visible.value = false
  stopDrag()
  await nextTick()
  launcher.value?.focus({ preventScroll: true })
}
function clampPosition(x, y) {
  const bounds = panel.value?.getBoundingClientRect()
  const width =
    bounds?.width || Math.min(wide.value ? 720 : 440, window.innerWidth - 48)
  const height =
    bounds?.height || Math.min(wide.value ? 820 : 660, window.innerHeight - 48)
  return {
    x: Math.max(8, Math.min(x, window.innerWidth - width - 8)),
    y: Math.max(8, Math.min(y, window.innerHeight - height - 8)),
  }
}
function syncDock() {
  const anchor = props.navigationAnchor
  const viewport = document.documentElement.clientWidth || window.innerWidth
  const width = Math.min(wide.value ? 720 : 440, viewport - 48)
  const edge = anchor?.isConnected ? anchor.getBoundingClientRect().right : 0
  dockRight.value =
    !mobile.value && edge >= width + 24 && edge <= viewport
      ? Math.max(24, viewport - edge)
      : 24
}
let anchorObserver = null
watch(
  () => props.navigationAnchor,
  (anchor) => {
    anchorObserver?.disconnect()
    if (anchor && typeof ResizeObserver !== 'undefined') {
      anchorObserver = new ResizeObserver(syncDock)
      anchorObserver.observe(anchor)
      if (anchor.parentElement) anchorObserver.observe(anchor.parentElement)
    }
    syncDock()
  },
  { immediate: true, flush: 'post' },
)
let dragOrigin = null
function startDrag(event) {
  if (
    mobile.value ||
    event.button !== 0 ||
    event.target.closest('button, a, input, textarea, select')
  )
    return
  const bounds = panel.value.getBoundingClientRect()
  dragOrigin = { x: event.clientX - bounds.left, y: event.clientY - bounds.top }
  dragging.value = true
  window.addEventListener('pointermove', moveDrag)
  window.addEventListener('pointerup', stopDrag)
  window.addEventListener('pointercancel', stopDrag)
  window.addEventListener('blur', stopDrag)
  event.preventDefault()
}
function moveDrag(event) {
  if (dragOrigin)
    position.value = clampPosition(
      event.clientX - dragOrigin.x,
      event.clientY - dragOrigin.y,
    )
}
function stopDrag() {
  dragging.value = false
  dragOrigin = null
  window.removeEventListener('pointermove', moveDrag)
  window.removeEventListener('pointerup', stopDrag)
  window.removeEventListener('pointercancel', stopDrag)
  window.removeEventListener('blur', stopDrag)
}
async function toggleSize() {
  wide.value = !wide.value
  await nextTick()
  syncDock()
  if (position.value)
    position.value = clampPosition(position.value.x, position.value.y)
}
function onResize() {
  mobile.value = window.innerWidth <= 700
  stopDrag()
  nextTick(syncDock)
  if (!mobile.value && position.value)
    position.value = clampPosition(position.value.x, position.value.y)
}
watch(
  () => props.attemptId,
  (id) => tutor.setAttempt(id),
  { immediate: true },
)
watch(
  () => [props.attemptId, state.value?.turns.length, state.value?.loaded],
  ([id, count], previous) => {
    if (visible.value) {
      unreadByAttempt.value[id] = false
      scrollToLatest()
    } else if (
      previous?.[0] === id &&
      previous[2] &&
      count > (previous[1] ?? count)
    )
      unreadByAttempt.value[id] = true
  },
)
onMounted(() => window.addEventListener('resize', onResize))
onBeforeUnmount(() => {
  anchorObserver?.disconnect()
  tutor.dispose()
  stopDrag()
  window.removeEventListener('resize', onResize)
})
</script>

<style scoped src="./tutor-window.css"></style>
