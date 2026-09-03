<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { detect, getHistory, getModels, type Detection, type ModelInfo } from './api'

const models = ref<ModelInfo[]>([])
const history = ref<Detection[]>([])
const selectedModel = ref('cae')
const category = ref('bottle')
const file = ref<File | null>(null)
const preview = ref('')
const result = ref<Detection | null>(null)
const busy = ref(false)
const message = ref('')

const currentModel = computed(() => models.value.find(item => item.name === selectedModel.value))

function chooseFile(event: Event) {
  const target = event.target as HTMLInputElement
  file.value = target.files?.[0] ?? null
  result.value = null
  message.value = ''
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = file.value ? URL.createObjectURL(file.value) : ''
}

async function runDetection() {
  if (!file.value) { message.value = '请先选择待检测图片'; return }
  busy.value = true
  message.value = ''
  try {
    result.value = await detect(file.value, selectedModel.value, category.value)
    history.value = await getHistory()
  } catch (error: any) {
    message.value = error.response?.data?.detail ?? '检测请求失败，请检查后端服务'
  } finally {
    busy.value = false
  }
}

onMounted(async () => {
  try {
    models.value = await getModels()
    history.value = await getHistory()
  } catch { message.value = '后端服务尚未启动' }
})
</script>

<template>
  <div class="app-shell">
    <header class="topbar">
      <div><p class="eyebrow">INDUSTRIAL VISION</p><h1>工业表面缺陷检测系统</h1></div>
      <span class="status"><i></i> 本地推理平台</span>
    </header>
    <main>
      <section class="hero card">
        <div><span class="tag">四模型对比</span><h2>从异常判断到像素级定位</h2><p>统一调用 CAE、PaDiM、PatchCore 与 STFPM，输出异常分数、热力图与推理耗时。</p></div>
        <div class="metric"><strong>4</strong><span>独立模型业务线</span></div>
      </section>

      <section class="workspace">
        <article class="card controls">
          <h3>检测参数</h3>
          <label>产品类别<select v-model="category"><option value="bottle">瓶体 Bottle</option><option value="tile">瓷砖 Tile</option><option value="transistor">晶体管 Transistor</option></select></label>
          <label>检测模型<select v-model="selectedModel"><option v-for="item in models" :key="item.name" :value="item.name">{{ item.title }} · {{ item.owner }}</option></select></label>
          <div v-if="currentModel" class="model-note"><span :class="['dot', currentModel.ready && 'ready']"></span>{{ currentModel.ready ? '模型已就绪' : '模型等待训练' }}</div>
          <label class="upload"><input type="file" accept="image/*" @change="chooseFile" /><span>选择检测图片</span><small>{{ file?.name || 'PNG / JPG / BMP' }}</small></label>
          <button :disabled="busy" @click="runDetection">{{ busy ? '正在分析…' : '开始检测' }}</button>
          <p v-if="message" class="error">{{ message }}</p>
        </article>

        <article class="card viewer">
          <div class="viewer-head"><h3>检测视图</h3><span v-if="result" :class="result.is_anomaly ? 'danger' : 'success'">{{ result.is_anomaly ? '发现异常' : '产品正常' }}</span></div>
          <div class="images">
            <div><p>原始图像</p><img v-if="preview" :src="preview" /><div v-else class="placeholder">等待上传</div></div>
            <div><p>异常热力图</p><img v-if="result" :src="result.heatmap_url" /><div v-else class="placeholder">等待检测</div></div>
          </div>
          <div v-if="result" class="result-grid"><div><span>异常分数</span><strong>{{ (result.anomaly_score * 100).toFixed(1) }}%</strong></div><div><span>推理耗时</span><strong>{{ result.inference_ms.toFixed(1) }} ms</strong></div><div><span>检测模型</span><strong>{{ result.model_name.toUpperCase() }}</strong></div></div>
        </article>
      </section>

      <section class="card history">
        <div class="section-head"><div><p class="eyebrow">RECENT INSPECTIONS</p><h3>检测历史</h3></div><span>{{ history.length }} 条记录</span></div>
        <table><thead><tr><th>文件</th><th>类别</th><th>模型</th><th>结果</th><th>异常分数</th><th>耗时</th></tr></thead><tbody><tr v-for="item in history" :key="item.id"><td>{{ item.filename }}</td><td>{{ item.category }}</td><td>{{ item.model_name }}</td><td><span :class="item.is_anomaly ? 'danger' : 'success'">{{ item.is_anomaly ? '异常' : '正常' }}</span></td><td>{{ (item.anomaly_score * 100).toFixed(1) }}%</td><td>{{ item.inference_ms.toFixed(1) }} ms</td></tr><tr v-if="!history.length"><td colspan="6" class="empty">暂无检测记录</td></tr></tbody></table>
      </section>
    </main>
  </div>
</template>

