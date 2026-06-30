import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || 'http://localhost:5000';

const api = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

export const uploadAndTransform = async (files, config) => {
  const formData = new FormData();
  files.forEach(file => {
    formData.append('files', file);
  });
  formData.append('config', JSON.stringify(config));

  const response = await api.post('/api/transform', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  });
  return response.data;
};

export const getConfigs = async () => {
  const response = await api.get('/api/configs');
  return response.data;
};

export const getSchema = async () => {
  const response = await api.get('/api/schema');
  return response.data;
};

export const healthCheck = async () => {
  try {
    const response = await api.get('/health');
    return response.data;
  } catch (error) {
    throw new Error('Backend Server Not Available');
  }
};

export default api;
