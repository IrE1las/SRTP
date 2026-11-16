<template>
  <main class="chapter-bank" :class="{ 'has-floating-tutor': chapterId }">
    <header class="bank-heading">
      <div>
        <h1>客观题库</h1>
        <p>按章节自主练习，提交后核对答案、回看解析。</p>
      </div>
      <router-link class="outline-link" to="/student/chapter-bank/all"
        >全部题目表格</router-link
      >
    </header>
    <div v-if="chaptersError" class="bank-error" role="alert">
      {{ chaptersError }}<button @click="loadChapters">重新加载目录</button>
    </div>
    <template v-if="!chapterId">
      <section class="overview-strip" aria-label="我的学习进度">
        <div>
          <strong>{{ totals.total }}</strong><span>题可练习</span>
        </div>
        <div>
          <strong>{{ totals.attempted }}</strong><span>题已作答</span>
        </div>
        <div>
          <strong>{{ totals.correct }}</strong><span>题曾做对</span>
        </div>
        <p>可以跳题、反复练习，也可以从标记的题目开始复习。</p>
      </section>
      <section
        v-loading="chaptersLoading"
        class="chapter-grid"
        aria-label="章节目录"
        :aria-busy="chaptersLoading"
      >
        <article
          v-for="chapter in chapters"
          :key="chapter.id"
          class="chapter-card"
        >
          <router-link class="chapter-main-link" :to="chapterPath(chapter.id)"
            ><div class="card-top">
              <span>第 {{ chapter.id }} 章</span
              ><span>{{ chapter.available }} 题</span>
            </div>
            <h2>{{ chapter.title }}</h2>
            <progress
              :value="chapter.attempted"
              :max="chapter.available || 1"
              :aria-label="`第 ${chapter.id} 章作答进度`"
            ></progress>
            <div class="card-progress">
              <span
                >已作答 {{ chapter.attempted || 0 }} /
                {{ chapter.available }}</span
              ><span>曾做对 {{ chapter.ever_correct || 0 }} 题</span>
            </div>
            <div class="card-bottom">
              <span>{{
                chapter.attempted ? '继续学习' : '浏览本章题目'
              }}</span><span aria-hidden="true">→</span>
            </div></router-link
          >
          <router-link class="marked-entry" :to="chapterPath(chapter.id, true)"
            >☆ 标记复习<span>{{ chapter.bookmarked }} 题</span></router-link
          >
        </article>
      </section>
      <el-empty
        v-if="!chaptersLoading && !chaptersError && !chapters.length"
        description="暂无章节资料"
      />
    </template>
    <div v-else class="study-layout">
      <aside class="chapter-sidebar" aria-label="切换章节">
        <router-link class="directory-link" to="/student/chapter-bank"
          >← 章节总览</router-link
        >
        <nav>
          <router-link
            v-for="chapter in chapters"
            :key="chapter.id"
            :to="chapterPath(chapter.id)"
            :class="{ active: String(chapter.id) === chapterId }"
            :aria-current="
              String(chapter.id) === chapterId ? 'page' : undefined
            "
            ><span class="sidebar-chapter">第 {{ chapter.id }} 章</span
            ><strong>{{ chapter.title }}</strong
            ><span class="sidebar-count"
              >{{ chapter.attempted || 0 }} /
              {{ chapter.available }} 已作答</span
            ></router-link
          >
        </nav>
      </aside>
      <section class="study-main" :aria-busy="loading">
        <header class="chapter-heading">
          <div>
            <span>第 {{ chapterId }} 章</span>
            <h2>{{ currentChapter?.title || '章节练习' }}</h2>
          </div>
        </header>
        <div class="chapter-progress">
          <span>共 {{ stats.total }} 题</span
          ><span
            >已作答 <b>{{ stats.attempted }}</b></span
          ><span
            >曾做对 <b>{{ stats.correct }}</b></span
          ><span
            >已标记 <b>{{ stats.marked }}</b></span
          >
        </div>
        <section class="study-toolbar" aria-label="筛选本章题目">
          <div class="progress-tabs" role="group" aria-label="按学习状态筛选">
            <button
              v-for="tab in progressTabs"
              :key="tab.value"
              :aria-pressed="filters.progress === tab.value"
              @click="applyFilters({ progress: tab.value })"
            >
              {{ tab.label }}
            </button>
          </div>
          <div class="search-row">
            <label
              ><span class="sr-only">按题型筛选</span
              ><select
                :value="filters.kind"
                @change="applyFilters({ kind: $event.target.value })"
              >
                <option value="">全部题型</option>
                <option
                  v-for="kind in kinds"
                  :key="kind.value"
                  :value="kind.value"
                >
                  {{ kind.label }}
                </option>
              </select></label
            ><label class="question-search"
              ><span class="sr-only">搜索本章题目</span
              ><input
                :value="filters.search"
                type="search"
                placeholder="搜索本章题干或题号"
                maxlength="150"
                @input="applyFilters({ search: $event.target.value })" /></label
            ><span class="filter-count">{{ filtered.length }} 题</span>
          </div>
        </section>
        <div v-if="error" class="bank-error" role="alert">
          {{ error }}<button @click="study.load()">重试加载</button>
        </div>
        <p v-if="loading" class="loading-message" role="status">
          正在加载本章题目…
        </p>
        <div v-else-if="!filtered.length && !error" class="empty-panel">
          <h3>
            {{ entries.length ? '没有符合条件的题目' : '本章暂无可练习题目' }}
          </h3>
          <p>
            {{
              filters.progress === 'marked'
                ? '在题目右上角标记需要复习的内容，下次可以在这里找到。'
                : '可以调整筛选条件，或选择其他章节继续学习。'
            }}
          </p>
          <button
            v-if="entries.length"
            @click="applyFilters({ kind: '', progress: '', search: '' })"
          >
            查看本章全部题目
          </button>
        </div>
        <div v-else-if="current" class="question-stage">
          <StudyQuestion
            :key="current.question.id"
            :entry="current"
            :number="entries.indexOf(current) + 1"
            @submit="study.submit"
            @bookmark="study.toggleBookmark"
            @retry="study.retry"
          />
        </div>
        <nav
          v-if="current && !loading"
          class="practice-nav"
          aria-label="切换练习题目"
        >
          <button :disabled="currentIndex <= 0" @click="study.move(-1)">
            ← 上一题</button
          ><span>{{ currentIndex + 1 }} / {{ filtered.length }}</span
          ><button
            :disabled="currentIndex >= filtered.length - 1"
            @click="study.move(1)"
          >
            下一题 →
          </button>
        </nav>
      </section>
      <aside
        ref="questionNavigation"
        class="answer-sidebar"
        aria-label="本章题目导航"
      >
        <div class="answer-card" :class="{ expanded: navigationOpen }">
          <h2>
            题目导航 <span>{{ filtered.length }} 题</span
            ><button
              class="mobile-nav-toggle"
              :aria-expanded="navigationOpen"
              aria-controls="chapter-number-grid"
              @click="navigationOpen = !navigationOpen"
            >
              {{ navigationOpen ? '收起' : '展开' }}
            </button>
          </h2>
          <p>点击题号自由跳转，无需按顺序作答。</p>
          <div class="legend">
            <span><i></i>未作答</span><span><i class="draft"></i>有草稿</span
            ><span><i class="wrong"></i>尚未做对</span
            ><span><i class="correct"></i>曾做对</span>
          </div>
          <nav
            id="chapter-number-grid"
            class="number-grid"
            aria-label="选择题号"
          >
            <button
              v-for="entry in filtered"
              :key="entry.question.id"
              :class="[
                numberClass(entry),
                {
                  selected: current?.question.id === entry.question.id,
                  marked: entry.marked,
                },
              ]"
              :aria-label="`第 ${entries.indexOf(entry) + 1} 题，${studyState(entry)}${entry.marked ? '，已标记' : ''}`"
              :aria-current="
                current?.question.id === entry.question.id ? 'true' : undefined
              "
              @click="jump(entry.question.id)"
            >
              {{ entries.indexOf(entry) + 1
              }}<span v-if="entry.marked" aria-hidden="true">★</span>
            </button>
          </nav>
          <p class="saving-note">
            提交记录与标记随账号保存。未提交草稿在当前页面内保留。
          </p>
        </div>
      </aside>
    </div>
    <ChapterAiTutor
      v-if="chapterId"
      :attempt-id="current?.attempt?.submitted ? current.attempt.id : ''"
      :question-label="
        current
          ? `第${chapterId}章 第${entries.indexOf(current) + 1}题`
          : `第${chapterId}章`
      "
      :question-stem="current?.question.stem || ''"
      :question-loading="loading"
      :navigation-anchor="questionNavigation"
    />
  </main>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import request from '@/utils/request'
import StudyQuestion from './StudyQuestion.vue'
import ChapterAiTutor from './ChapterAiTutor.vue'
import { createChapterStudy, hasDraft, studyState } from './useChapterStudy.js'
import { errorText, QUESTION_KINDS } from './presentation.js'
const route = useRoute()
const chapterId = computed(() => String(route.params.chapterId || ''))
const chapters = ref([]),
  chaptersLoading = ref(false),
  chaptersError = ref('')
const navigationOpen = ref(false)
const questionNavigation = ref(null)
let chapterRequest = 0
const currentChapter = computed(() =>
  chapters.value.find((chapter) => String(chapter.id) === chapterId.value),
)
const totals = computed(() =>
  chapters.value.reduce(
    (sum, c) => ({
      total: sum.total + (c.available || 0),
      attempted: sum.attempted + (c.attempted || 0),
      correct: sum.correct + (c.ever_correct || 0),
    }),
    { total: 0, attempted: 0, correct: 0 },
  ),
)
const chapterPath = (id, marked = false) => ({
  path: `/student/chapter-bank/${id}`,
  query: marked ? { marked: '1' } : {},
})
const study = createChapterStudy({
  get: (...args) => request.get(...args),
  post: (...args) => request.post(...args),
  put: (...args) => request.put(...args),
  onProgressChange: loadChapters,
})
const {
  entries,
  filtered,
  current,
  filters,
  loading,
  error,
  stats,
  applyFilters,
} = study
const currentIndex = computed(() => filtered.value.indexOf(current.value))
const kinds = QUESTION_KINDS.filter((kind) =>
  ['choice', 'multi', 'true_false', 'cell'].includes(kind.value),
)
const progressTabs = [
  { value: '', label: '全部题目' },
  { value: 'unanswered', label: '未作答' },
  { value: 'not_correct', label: '尚未做对' },
  { value: 'correct', label: '曾做对' },
  { value: 'marked', label: '已标记' },
]
function numberClass(entry) {
  if (entry.ever_correct) return 'correct'
  if (entry.attempted) return 'wrong'
  return !entry.attempt?.submitted && hasDraft(entry.draft) ? 'draft' : ''
}
async function jump(id) {
  study.select(id)
  await nextTick()
  const element = document.getElementById(`study-question-${id}`)
  element?.scrollIntoView({ behavior: 'instant', block: 'start' })
  element?.focus({ preventScroll: true })
}
async function loadChapters() {
  const serial = ++chapterRequest
  chaptersLoading.value = true
  chaptersError.value = ''
  try {
    const result = await request.get('/chapter-bank/practice/chapters')
    if (serial === chapterRequest)
      chapters.value = Array.isArray(result) ? result : []
  } catch (failure) {
    if (serial === chapterRequest)
      chaptersError.value = errorText(failure, '目录加载失败，请重试。')
  } finally {
    if (serial === chapterRequest) chaptersLoading.value = false
  }
}
watch(
  [chapterId, () => route.query.marked],
  ([id, marked]) => study.setChapter(id, marked === '1'),
  { immediate: true },
)
loadChapters()
onBeforeUnmount(() => {
  chapterRequest++
  study.dispose()
})
</script>

<style scoped src="./study.css"></style>
