import request from '@/utils/request'

const base = '/admin/knowledge'
export const listMaterials = () => request.get(base)
export const getMaterial = (id) => request.get(`${base}/${id}`)
export const uploadMaterial = (body) =>
  request.post(base, body, { timeout: 60000 })
export const editMaterial = (id, body) => request.put(`${base}/${id}`, body)
export const deleteMaterial = (id, revision) =>
  request.delete(`${base}/${id}`, { params: { revision } })
export const downloadMaterial = (id) =>
  request.get(`${base}/${id}/download`, { responseType: 'blob' })
