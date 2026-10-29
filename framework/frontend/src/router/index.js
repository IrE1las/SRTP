import { createRouter, createWebHistory } from 'vue-router'
import AppLayout from '@/layout/AppLayout.vue'
import { useUserStore } from '@/store/user'
import { roleHomeMap } from '@/ui/navigation'
export { roleHomeMap }

const profile = () => import('@/views/shared/ProfileHome.vue')
const theory = () => import('@/views/student/LabTopics.vue')
const questions = () => import('@/views/teacher/TheoryStudentList.vue')
const children = [
  { path: '', redirect: () => roleHomeMap[useUserStore().role] || '/login' },
  { path: 'student', redirect: '/student/dashboard', meta: { roles: ['student'] } },
  { path: 'student/dashboard', component: profile, meta: { roles: ['student'] } },
  { path: 'student/learn', redirect: '/student/learn/theory', meta: { roles: ['student'] } },
  { path: 'student/learn/theory', component: theory, meta: { roles: ['student'] } },
  { path: 'student/learn/theory/attempts', component: () => import('@/views/student/TheoryHistory.vue'), meta: { roles: ['student'] } },
  { path: 'student/learn/theory/attempts/:attemptId([0-9]+)', component: () => import('@/views/student/TheoryAttemptDetail.vue'), meta: { roles: ['student'] } },
  { path: 'student/learn/theory/:topicId([1-6])', component: () => import('@/views/student/TheoryTopic.vue'), meta: { roles: ['student'] } },
  { path: 'student/learn/operations', component: () => import('@/views/student/OperationCatalogue.vue'), meta: { roles: ['student'] } },
  { path: 'student/learn/operations/history', component: () => import('@/views/student/OperationHistory.vue'), meta: { roles: ['student'] } },
  { path: 'student/learn/operations/attempts/:attemptId', component: () => import('@/views/student/OperationAttempt.vue'), meta: { roles: ['student'] } },
  { path: 'operations/reviews', component: () => import('@/views/teacher/OperationReviews.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'operations/reviews/:attemptId', component: () => import('@/views/teacher/OperationAttemptReview.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'operations/manage', component: () => import('@/views/teacher/OperationQuestions.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'operations/manage/new', component: () => import('@/views/teacher/OperationEditor.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'operations/manage/:questionId([0-9]+)/edit', component: () => import('@/views/teacher/OperationEditor.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'operations/manage/:questionId([0-9]+)/review', component: () => import('@/views/teacher/OperationReview.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'student/exams', component: () => import('@/views/student/Exams.vue'), meta: { roles: ['student'] } },
  { path: 'student/exams/history', component: () => import('@/views/student/ExamHistory.vue'), meta: { roles: ['student'] } },
  { path: 'teacher', redirect: '/teacher/dashboard', meta: { roles: ['teacher'] } },
  { path: 'teacher/dashboard', component: profile, meta: { roles: ['teacher'] } },
  { path: 'teacher/questions', component: questions, meta: { roles: ['teacher'] } },
  { path: 'teacher/questions/students/:studentId', component: () => import('@/views/teacher/TheoryStudentAttempts.vue'), meta: { roles: ['teacher'] } },
  { path: 'teacher/questions/attempts/:attemptId', component: () => import('@/views/teacher/TheoryReview.vue'), meta: { roles: ['teacher'] } },
  { path: 'teacher/exams', component: () => import('@/views/teacher/Exams.vue'), meta: { roles: ['teacher'] } },
  { path: 'exams/manage', component: () => import('@/views/teacher/Exams.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'exams/manage/new', component: () => import('@/views/teacher/ExamEditor.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'exams/manage/:examId([0-9]+)', component: () => import('@/views/teacher/ExamEditor.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'exams/manage/attempts/:attemptId', component: () => import('@/views/teacher/ExamAttempt.vue'), meta: { roles: ['teacher','admin'] } },
  { path: 'admin', component: profile, meta: { roles: ['admin'] } },
  { path: 'admin/users', component: () => import('@/views/admin/UserManagement.vue'), meta: { roles: ['admin'] } },
  { path: 'admin/ai-settings', component: () => import('@/views/admin/AiSettings.vue'), meta: { roles: ['admin'] } },
]
const router = createRouter({ history: createWebHistory(), scrollBehavior(to,from,savedPosition) { return savedPosition || {left:0,top:0} }, routes: [
  { path: '/login', component: () => import('@/views/auth/Login.vue') },
  { path: '/operations/manage/:questionId([0-9]+)/record', component: () => import('@/views/teacher/OperationWorkspace.vue'), meta: { requiresAuth: true, roles: ['teacher','admin'] } },
  { path: '/student/exams/attempts/:attemptId', component: () => import('@/views/student/ExamAttempt.vue'), meta: { requiresAuth: true, roles: ['student'], examStandalone: true } },
  { path: '/', component: AppLayout, meta: { requiresAuth: true }, children },
  { path: '/:pathMatch(.*)*', component: () => import('@/views/shared/NotFound.vue'), meta: { requiresAuth: true } },
] })
router.beforeEach(to => {
  const user = useUserStore()
  if (to.matched.some(r => r.meta.requiresAuth) && !user.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath } }
  if (to.path === '/login' && user.isLoggedIn) return roleHomeMap[user.role] || '/'
  if (to.meta.roles && !to.meta.roles.includes(user.role)) return roleHomeMap[user.role] || '/login'
  return true
})
export default router
