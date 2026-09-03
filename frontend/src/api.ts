import axios from 'axios'

export interface ModelInfo {
  name: string
  owner: string
  title: string
  requires_training: boolean
  ready: boolean
}

export interface Detection {
  id: number
  filename: string
  category: string
  model_name: string
  anomaly_score: number
  is_anomaly: boolean
  inference_ms: number
  original_url: string
  heatmap_url: string
  created_at: string
}

export const api = axios.create({ baseURL: '/' })

export async function getModels() {
  return (await api.get<ModelInfo[]>('/api/models')).data
}

export async function getHistory() {
  return (await api.get<Detection[]>('/api/detections')).data
}

export async function detect(file: File, model: string, category: string) {
  const form = new FormData()
  form.append('file', file)
  form.append('model_name', model)
  form.append('category', category)
  return (await api.post<Detection>('/api/detections', form)).data
}

