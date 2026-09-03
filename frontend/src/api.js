import axios from 'axios';
export const api = axios.create({ baseURL: '/' });
export async function getModels() {
    return (await api.get('/api/models')).data;
}
export async function getHistory() {
    return (await api.get('/api/detections')).data;
}
export async function detect(file, model, category) {
    const form = new FormData();
    form.append('file', file);
    form.append('model_name', model);
    form.append('category', category);
    return (await api.post('/api/detections', form)).data;
}
