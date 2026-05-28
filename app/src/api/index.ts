/**
 * API 封装
 * 与服务器通信的所有接口
 */
import axios from 'axios';
import {SERVER_CONFIG} from '../config';

const api = axios.create({
  baseURL: SERVER_CONFIG.BASE_URL + '/api',
  timeout: SERVER_CONFIG.TIMEOUT,
  headers: {'Content-Type': 'application/json'},
});

// ========== 设备接口 ==========
export const deviceApi = {
  /** 获取设备列表 */
  listDevices: () => api.get('/devices/'),

  /** 获取设备详情（含最新传感器数据） */
  getDevice: (deviceId: string) => api.get(`/devices/${deviceId}`),

  /** 控制水泵 */
  controlPump: (deviceId: string, action: 'on' | 'off', duration?: number) =>
    api.post(`/devices/${deviceId}/pump`, {action, duration: duration ?? 30}),
};

// ========== 传感器历史数据接口 ==========
export const sensorApi = {
  /** 获取历史数据（用于绘图） */
  getHistory: (deviceId: string, hours: number = 24) =>
    api.get(`/sensor/${deviceId}/history`, {params: {hours}}),

  /** 获取统计数据 */
  getStats: (deviceId: string, hours: number = 24) =>
    api.get(`/sensor/${deviceId}/stats`, {params: {hours}}),
};

// ========== 水泵操作记录 ==========
export const pumpApi = {
  getLogs: (deviceId: string, days: number = 7) =>
    api.get(`/pump/${deviceId}/logs`, {params: {days}}),
};

// ========== 告警接口 ==========
export const alertApi = {
  getAlerts: (deviceId: string, days: number = 7, unreadOnly: boolean = false) =>
    api.get(`/alerts/${deviceId}/list`, {params: {days, unread_only: unreadOnly}}),

  markRead: (deviceId: string, alertId: number) =>
    api.post(`/alerts/${deviceId}/read/${alertId}`),

  getRules: (deviceId: string) => api.get(`/alerts/${deviceId}/rules`),

  upsertRule: (deviceId: string, ruleType: string, threshold: number, enabled: boolean) =>
    api.post(`/alerts/${deviceId}/rules`, {rule_type: ruleType, threshold, enabled}),
};

// ========== 自动规则接口 ==========
export const ruleApi = {
  getRules: (deviceId: string) => api.get(`/rules/${deviceId}`),

  createRule: (deviceId: string, rule: {
    rule_name: string;
    condition_type: string;
    condition_operator: string;
    condition_value: number;
    action_duration: number;
    enabled: boolean;
  }) => api.post(`/rules/${deviceId}`, rule),

  deleteRule: (deviceId: string, ruleId: number) =>
    api.delete(`/rules/${deviceId}/${ruleId}`),
};

export default api;
