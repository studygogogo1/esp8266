// 服务器配置
// 修改为你的服务器实际 IP 和端口
export const SERVER_CONFIG = {
  BASE_URL: 'http://192.168.1.100:8000',  // 改成你的服务器IP
  WS_URL: 'ws://192.168.1.100:8000/ws',   // WebSocket 地址
  TIMEOUT: 10000,
};

// 默认设备 ID（从华为云控制台获取）
export const DEFAULT_DEVICE_ID = 'your-device-id-here';
