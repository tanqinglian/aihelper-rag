/**
 * API 客户端
 */
const BASE_URL = 'http://localhost:8900';

/**
 * 通用请求函数
 */
async function request(path, options = {}) {
  const url = `${BASE_URL}${path}`;
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  return response.json();
}

/**
 * 项目相关 API
 */
export const projectApi = {
  // 获取项目列表
  list: () => request('/projects'),

  // 创建项目
  create: (data) =>
    request('/projects', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // 获取项目详情
  get: (id) => request(`/projects/${id}`),

  // 更新项目
  update: (id, data) =>
    request(`/projects/${id}`, {
      method: 'PUT',
      body: JSON.stringify(data),
    }),

  // 删除项目
  delete: (id) =>
    request(`/projects/${id}`, {
      method: 'DELETE',
    }),

  // 验证路径
  validatePath: (path) => request(`/validate-path?path=${encodeURIComponent(path)}`),
};

/**
 * 索引相关 API (SSE)
 */
export const indexApi = {
  // 开始索引（返回 EventSource URL）
  getIndexUrl: (projectId) => `${BASE_URL}/projects/${projectId}/index`,
};

/**
 * 问答相关 API
 */
export const chatApi = {
  // 流式问答（返回 fetch response 用于流式处理）
  askStream: (projectId, question, topK = 50) =>
    fetch(`${BASE_URL}/ask/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ project_id: projectId, question, top_k: topK }),
    }),
};

/**
 * 监控相关 API
 */
export const monitoringApi = {
  // 健康检查
  health: () => request('/health'),

  // Ollama 状态
  ollama: () => request('/monitoring/ollama'),

  // 系统统计
  stats: () => request('/monitoring/stats'),
};

export default {
  project: projectApi,
  index: indexApi,
  chat: chatApi,
  monitoring: monitoringApi,
};
