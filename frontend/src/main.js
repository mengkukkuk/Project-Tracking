import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useUiStore } from './stores/ui'
import './composables/macarons'
import './assets/main.css'

const app = createApp(App)
app.use(createPinia())
app.use(router)

// Apply persisted theme before first paint.
useUiStore().initTheme()

app.mount('#app')
