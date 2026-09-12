<template>
  <div class="ai-settings">
    <div class="settings-header">
      <h5 class="settings-title">
        <el-icon><Cpu /></el-icon>
        AI设置
      </h5>
      <el-button size="small" plain @click="goBack">
        <el-icon><ArrowLeft /></el-icon>
        返回
      </el-button>
    </div>

    <el-card shadow="never" class="settings-card">
      <template #header>
        <div class="card-header-content">
          <div class="header-icon">
            <el-icon><Cpu /></el-icon>
          </div>
          <div>
            <strong>AI 模型配置</strong>
            <div class="header-sub">配置 DeepSeek API 连接参数</div>
          </div>
        </div>
      </template>

      <el-alert
        v-if="alert.visible"
        :title="alert.message"
        :type="alert.type"
        show-icon
        :closable="true"
        class="alert-box"
        @close="alert.visible = false"
      />

      <el-form label-position="top" @submit.prevent>
        <el-form-item>
          <template #label>
            <span class="form-label-icon">
              <el-icon><Key /></el-icon>
              API Key
            </span>
          </template>
          <el-input
            v-model="form.apiKey"
            type="password"
            placeholder="sk-..."
            autocomplete="off"
            show-password
          />
          <div class="form-text">用于调用 AI 大模型的 API 密钥</div>
        </el-form-item>

        <el-form-item>
          <template #label>
            <span class="form-label-icon">
              <el-icon><Cpu /></el-icon>
              模型名称
            </span>
          </template>
          <el-input v-model="form.model" placeholder="例如：deepseek-v4-flash" />
          <div class="form-text">AI 模型标识，不同模型能力与价格不同</div>
        </el-form-item>

        <el-form-item>
          <template #label>
            <span class="form-label-icon">
              <el-icon><Connection /></el-icon>
              API 地址
            </span>
          </template>
          <el-input v-model="form.baseUrl" placeholder="https://api.deepseek.com" />
          <div class="form-text">AI 服务提供商的 API 端点地址</div>
        </el-form-item>

        <div class="actions">
          <el-button type="primary" @click="saveSettings">
            <el-icon><Check /></el-icon>
            保存配置
          </el-button>
          <el-button plain @click="testConnection">
            <el-icon><Lightning /></el-icon>
            测试连接
          </el-button>
        </div>
      </el-form>
    </el-card>

    <!-- 使用说明 -->
    <el-card shadow="never" class="settings-card">
      <template #header>
        <el-icon class="header-info"><InfoFilled /></el-icon>
        <strong>使用说明</strong>
      </template>
      <ul class="usage-list">
        <li class="mb-2"><strong>API Key</strong>：在 DeepSeek 官网 (platform.deepseek.com) 注册后获取</li>
        <li class="mb-2"><strong>模型名称</strong>：填写当前可用的模型标识，例如 <code>deepseek-v4-flash</code>。经典例题使用非思考模式组织已核验的解释内容。</li>
        <li class="mb-2"><strong>API 地址</strong>：默认为 <code>https://api.deepseek.com</code>，使用第三方代理时可修改</li>
        <li>保存后即时生效，无需重启服务</li>
      </ul>
    </el-card>
  </div>
</template>

<script setup>
import { onMounted, reactive } from 'vue'
import { useRouter } from 'vue-router'
import {
  ArrowLeft,
  Check,
  Connection,
  Cpu,
  InfoFilled,
  Key,
  Lightning,
} from '@element-plus/icons-vue'

import { getAiSettings, testAiConnection, updateAiSettings } from '@/api/settings'

const router = useRouter()

const form = reactive({ apiKey: '', model: '', baseUrl: '' })
const alert = reactive({ visible: false, type: 'info', message: '' })
let currentKeyMasked = ''

async function loadSettings() {
  const data = await getAiSettings()
  if (data) {
    form.apiKey = data.api_key_masked
    form.model = data.model
    form.baseUrl = data.base_url
    currentKeyMasked = data.api_key_masked
  }
}

async function saveSettings() {
  const apiKey = form.apiKey.trim()
  const model = form.model.trim()
  const baseUrl = form.baseUrl.trim()

  if (!apiKey) { showAlert('请输入 API Key', 'error'); return }
  if (!model) { showAlert('请输入模型名称', 'error'); return }
  if (!baseUrl) { showAlert('请输入 API 地址', 'error'); return }

  const body = { api_key: apiKey, model, base_url: baseUrl }
  // 如果 key 没改动（仍是掩码值），不传 key
  if (apiKey === currentKeyMasked) {
    delete body.api_key
  }

  try {
    const resp = await updateAiSettings(body)
    if (resp && resp.success) {
      showAlert('配置已保存并生效', 'success')
      loadSettings()
    } else {
      showAlert(resp?.message || '保存失败', 'error')
    }
  } catch (err) {
    // 请求失败时 axios 拦截器已弹出错误提示
    console.error(err)
  }
}

async function testConnection() {
  const model = form.model.trim()
  const baseUrl = form.baseUrl.trim()
  if (!model || !baseUrl) {
    showAlert('请先填写模型名称和 API 地址', 'warning')
    return
  }
  showAlert('正在测试连接...', 'info')
  try {
    const resp = await testAiConnection({ model, base_url: baseUrl })
    if (resp && resp.success) {
      showAlert('连接测试成功！模型响应正常', 'success')
    } else {
      showAlert('连接测试失败：' + (resp?.message || '请检查配置'), 'error')
    }
  } catch (err) {
    console.error(err)
  }
}

function goBack() {
  if (window.history.length > 1) {
    router.back()
  } else {
    router.push('/admin')
  }
}

function showAlert(msg, type) {
  alert.message = msg
  alert.type = type
  alert.visible = true
}

onMounted(loadSettings)
</script>

<style scoped>
.ai-settings {
  max-width: 760px;
  margin: 0 auto;
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.settings-title {
  display: flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: var(--ui-text-md);
}

.settings-card {
  margin-bottom: 16px;
}

.card-header-content {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 38px;
  height: 38px;
  border-radius: 50%;
  background: linear-gradient(135deg, #e8f0fe, #d2e3fc);
  color: #1a73e8;
  font-size: var(--ui-text-md);
}

.header-sub {
  margin-top: 2px;
  font-size: var(--ui-text-base);
  color: #586f82;
}

.header-info {
  margin-right: 6px;
  color: #586f82;
}

.alert-box {
  margin-bottom: 16px;
}

.form-label-icon {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}

.form-text {
  margin-top: 6px;
  font-size: var(--ui-text-base);
  color: #586f82;
}

.actions {
  display: flex;
  gap: 8px;
}

.usage-list {
  margin: 0;
  padding-left: 18px;
  font-size: var(--ui-text-base);
  color: #606266;
  line-height: 1.8;
}

.mb-2 {
  margin-bottom: 8px;
}
</style>
