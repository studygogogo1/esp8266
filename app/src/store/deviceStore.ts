/**
 * 全局设备状态管理（Zustand）
 */
import {create} from 'zustand';

export interface SensorData {
  temperature: number | null;
  humidity: number | null;
  soil_moisture: number | null;
  pump_status: boolean;
  wifi_signal: number | null;
  timestamp: string;
}

export interface AlertItem {
  type: string;
  message: string;
  value: number;
  threshold: number;
  time?: string;
}

export interface DeviceInfo {
  device_id: string;
  device_name: string;
  is_online: boolean;
  firmware_version: string;
  last_online: string | null;
}

interface DeviceStore {
  // 当前选中的设备
  currentDeviceId: string;
  setCurrentDeviceId: (id: string) => void;

  // 设备信息
  deviceInfo: DeviceInfo | null;
  setDeviceInfo: (info: DeviceInfo) => void;

  // 实时传感器数据
  realtimeData: SensorData | null;
  updateRealtimeData: (deviceId: string, data: SensorData) => void;

  // 告警列表（未读）
  unreadAlerts: AlertItem[];
  addAlert: (deviceId: string, alert: AlertItem) => void;
  clearAlerts: () => void;

  // 是否正在控制水泵
  pumpLoading: boolean;
  setPumpLoading: (loading: boolean) => void;
}

export const useDeviceStore = create<DeviceStore>((set, get) => ({
  currentDeviceId: '',
  setCurrentDeviceId: (id) => set({currentDeviceId: id}),

  deviceInfo: null,
  setDeviceInfo: (info) => set({deviceInfo: info}),

  realtimeData: null,
  updateRealtimeData: (deviceId, data) => {
    if (deviceId === get().currentDeviceId || !get().currentDeviceId) {
      set({realtimeData: data});
    }
  },

  unreadAlerts: [],
  addAlert: (deviceId, alert) => {
    if (deviceId === get().currentDeviceId || !get().currentDeviceId) {
      set(state => ({
        unreadAlerts: [alert, ...state.unreadAlerts].slice(0, 20),
      }));
    }
  },
  clearAlerts: () => set({unreadAlerts: []}),

  pumpLoading: false,
  setPumpLoading: (loading) => set({pumpLoading: loading}),
}));
