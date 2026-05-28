/**
 * WebSocket 实时数据连接
 * 用于接收服务器推送的实时传感器数据和告警
 */
import {SERVER_CONFIG} from '../config';
import {useDeviceStore} from '../store/deviceStore';

class WSClient {
  private ws: WebSocket | null = null;
  private reconnectTimer: any = null;
  private reconnectCount = 0;
  private maxReconnect = 10;

  connect() {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    console.log('WebSocket 连接中...');
    this.ws = new WebSocket(SERVER_CONFIG.WS_URL);

    this.ws.onopen = () => {
      console.log('WebSocket 已连接');
      this.reconnectCount = 0;
      // 开启心跳
      this.startHeartbeat();
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        this.handleMessage(msg);
      } catch (e) {
        // pong 消息不是 JSON，忽略
      }
    };

    this.ws.onclose = () => {
      console.log('WebSocket 断开，准备重连...');
      this.scheduleReconnect();
    };

    this.ws.onerror = (error) => {
      console.error('WebSocket 错误:', error);
    };
  }

  private handleMessage(msg: any) {
    const store = useDeviceStore.getState();

    if (msg.type === 'sensor_update') {
      // 更新实时传感器数据
      store.updateRealtimeData(msg.device_id, msg.data);
    } else if (msg.type === 'alert') {
      // 新告警
      store.addAlert(msg.device_id, msg.alert);
    }
  }

  private heartbeatTimer: any = null;
  private startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      if (this.ws?.readyState === WebSocket.OPEN) {
        this.ws.send('ping');
      }
    }, 30000); // 每 30 秒发一次心跳
  }

  private scheduleReconnect() {
    if (this.reconnectCount >= this.maxReconnect) return;
    const delay = Math.min(1000 * 2 ** this.reconnectCount, 30000);
    this.reconnectTimer = setTimeout(() => {
      this.reconnectCount++;
      this.connect();
    }, delay);
  }

  disconnect() {
    clearInterval(this.heartbeatTimer);
    clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }
}

export const wsClient = new WSClient();
