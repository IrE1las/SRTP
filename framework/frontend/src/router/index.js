import { createRouter, createWebHistory } from 'vue-router'

import AppLayout from '@/layout/AppLayout.vue'
import { useUserStore } from '@/store/user'

export const roleHomeMap = {
  student: '/student/dashboard',
  teacher: '/teacher/dashboard',
  admin: '/admin',
}

const routes = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/Login.vue'),
  },
  {
    path: '/',
    component: AppLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: () => {
          const userStore = useUserStore()
          return roleHomeMap[userStore.role] || '/login'
        },
      },
      {
        path: 'student',
        redirect: '/student/dashboard',
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/dashboard',
        name: 'StudentDashboard',
        component: () => import('@/views/student/Dashboard.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/lobby',
        name: 'ExerciseLobby',
        component: () => import('@/views/student/ExerciseLobby.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/shunting-questions',
        name: 'ShuntingQuestionBank',
        component: () => import('@/views/student/ShuntingQuestionBank.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/lab-topics',
        name: 'LabTopics',
        component: () => import('@/views/student/LabTopics.vue'),
        meta: { requiresAuth: true, roles: ['student', 'teacher'] },
      },
      {
        path: 'teacher/lab-topics',
        name: 'TeacherLabTopics',
        component: () => import('@/views/student/LabTopics.vue'),
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      {
        path: 'student/exercises/:id',
        name: 'ExerciseWorkbench',
        component: () => import('@/views/student/ExerciseWorkbench.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/history',
        name: 'ExerciseHistory',
        component: () => import('@/views/student/ExerciseHistory.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/history/:sessionId',
        name: 'ExerciseReplay',
        component: () => import('@/views/student/ExerciseReplay.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/interlocking-exam',
        name: 'InterlockingExam',
        component: () => import('@/views/student/InterlockingExam.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/interlocking-exam-protective',
        name: 'InterlockingExamProtective',
        component: () => import('@/views/student/InterlockingExamProtective.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/interlocking-exam-driven',
        name: 'InterlockingExamDriven',
        component: () => import('@/views/student/InterlockingExamDriven.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'student/interlocking-exam-conditional',
        name: 'InterlockingExamConditional',
        component: () => import('@/views/student/InterlockingExamConditional.vue'),
        meta: { requiresAuth: true, roles: ['student'] },
      },
      {
        path: 'teacher',
        redirect: '/teacher/dashboard',
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      {
        path: 'teacher/dashboard',
        name: 'TeacherDashboard',
        component: () => import('@/views/teacher/Dashboard.vue'),
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      {
        path: 'teacher/exercises',
        name: 'TeacherExerciseList',
        component: () => import('@/views/teacher/ExerciseList.vue'),
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      {
        path: 'teacher/exercises/new',
        name: 'TeacherExerciseCreate',
        component: () => import('@/views/teacher/ExerciseEditor.vue'),
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      {
        path: 'teacher/exercises/:id/edit',
        name: 'TeacherExerciseEdit',
        component: () => import('@/views/teacher/ExerciseEditor.vue'),
        meta: { requiresAuth: true, roles: ['teacher'] },
      },
      { path: 'admin/questions', name: 'AdminQuestionBank', component: () => import('@/views/admin/QuestionBank.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
      { path: 'admin/questions/new', name: 'AdminQuestionCreate', component: () => import('@/views/admin/QuestionEditor.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
      { path: 'admin/questions/:id', name: 'AdminQuestionEdit', component: () => import('@/views/admin/QuestionEditor.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
      { path: 'admin/grading', name: 'AdminGrading', component: () => import('@/views/teacher/GradingWorkbench.vue'), meta: { requiresAuth: true, roles: ['admin'] } },
      { path: 'teacher/grading', name: 'TeacherGrading', component: () => import('@/views/teacher/GradingWorkbench.vue'), meta: { requiresAuth: true, roles: ['teacher'] } },
      {
        path: 'admin',
        name: 'AdminDashboard',
        component: () => import('@/views/admin/Dashboard.vue'),
        meta: { requiresAuth: true, roles: ['admin'] },
      },
      {
        path: 'admin/ai-settings',
        name: 'AdminAiSettings',
        component: () => import('@/views/admin/AiSettings.vue'),
        meta: { requiresAuth: true, roles: ['admin'] },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  const userStore = useUserStore()
  const requiresAuth = to.matched.some((record) => record.meta.requiresAuth)
  const allowedRoles = to.matched.flatMap((record) => record.meta.roles || [])

  if (!requiresAuth && to.path === '/login' && userStore.isLoggedIn) {
    return roleHomeMap[userStore.role] || '/'
  }

  if (requiresAuth && !userStore.isLoggedIn) {
    return { path: '/login', query: { redirect: to.fullPath } }
  }

  if (allowedRoles.length > 0 && userStore.role !== 'admin' && !allowedRoles.includes(userStore.role)) {
    return roleHomeMap[userStore.role] || '/login'
  }

  return true
})

export default router
