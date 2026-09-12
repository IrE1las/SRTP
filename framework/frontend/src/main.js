import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'

import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'
import { useUserStore } from './store/user'
import './style.css'
import './readability.css'

const app = createApp(App)
const pinia = createPinia()

app.use(pinia)
app.use(router)
app.use(ElementPlus)

const userStore = useUserStore()
userStore.restoreAuth()

app.mount('#app')
