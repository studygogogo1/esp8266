/**
 * 首页 - 实时仪表盘
 * 显示：温度、湿度、土壤湿度、水泵控制
 */
import React, {useEffect, useState, useCallback} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  RefreshControl,
  Alert,
  ActivityIndicator,
} from 'react-native';
import {useDeviceStore} from '../store/deviceStore';
import {deviceApi} from '../api';
import {DEFAULT_DEVICE_ID} from '../config';

// 传感器卡片
const SensorCard = ({
  label,
  value,
  unit,
  icon,
  color,
  warningMin,
  warningMax,
}: {
  label: string;
  value: number | null;
  unit: string;
  icon: string;
  color: string;
  warningMin?: number;
  warningMax?: number;
}) => {
  const isWarning =
    value !== null &&
    ((warningMin !== undefined && value < warningMin) ||
      (warningMax !== undefined && value > warningMax));

  return (
    <View style={[styles.sensorCard, isWarning && styles.sensorCardWarning]}>
      <Text style={styles.sensorIcon}>{icon}</Text>
      <Text style={[styles.sensorValue, {color: isWarning ? '#FF4444' : color}]}>
        {value !== null ? value.toFixed(1) : '--'}
      </Text>
      <Text style={styles.sensorUnit}>{unit}</Text>
      <Text style={styles.sensorLabel}>{label}</Text>
      {isWarning && <Text style={styles.warningDot}>⚠️</Text>}
    </View>
  );
};

// 水泵控制按钮
const PumpControl = ({
  isOn,
  loading,
  onToggle,
}: {
  isOn: boolean;
  loading: boolean;
  onToggle: (action: 'on' | 'off') => void;
}) => (
  <View style={styles.pumpCard}>
    <View style={styles.pumpHeader}>
      <Text style={styles.pumpTitle}>💧 水泵控制</Text>
      <View style={[styles.pumpStatus, isOn ? styles.pumpOn : styles.pumpOff]}>
        <Text style={styles.pumpStatusText}>{isOn ? '运行中' : '已停止'}</Text>
      </View>
    </View>
    <View style={styles.pumpButtons}>
      <TouchableOpacity
        style={[styles.pumpBtn, styles.pumpBtnOn, isOn && styles.pumpBtnDisabled]}
        onPress={() => onToggle('on')}
        disabled={isOn || loading}>
        {loading && !isOn ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.pumpBtnText}>开启水泵</Text>
        )}
      </TouchableOpacity>
      <TouchableOpacity
        style={[styles.pumpBtn, styles.pumpBtnOff, !isOn && styles.pumpBtnDisabled]}
        onPress={() => onToggle('off')}
        disabled={!isOn || loading}>
        {loading && isOn ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.pumpBtnText}>关闭水泵</Text>
        )}
      </TouchableOpacity>
    </View>
  </View>
);

export default function DashboardScreen() {
  const {realtimeData, deviceInfo, setDeviceInfo, setPumpLoading, pumpLoading} =
    useDeviceStore();
  const [refreshing, setRefreshing] = useState(false);
  const deviceId = DEFAULT_DEVICE_ID;

  const fetchDevice = useCallback(async () => {
    try {
      const resp = await deviceApi.getDevice(deviceId);
      setDeviceInfo(resp.data);
    } catch (e) {
      console.error('获取设备信息失败', e);
    }
  }, [deviceId]);

  useEffect(() => {
    fetchDevice();
  }, [fetchDevice]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchDevice();
    setRefreshing(false);
  };

  const handlePumpToggle = async (action: 'on' | 'off') => {
    setPumpLoading(true);
    try {
      await deviceApi.controlPump(deviceId, action, 30);
      Alert.alert('成功', action === 'on' ? '水泵已开启（30秒后自动关闭）' : '水泵已关闭');
      await fetchDevice();
    } catch (e: any) {
      Alert.alert('失败', e?.response?.data?.detail || '操作失败，请检查网络');
    } finally {
      setPumpLoading(false);
    }
  };

  // 优先使用 WebSocket 实时数据，否则用接口返回数据
  const temp = realtimeData?.temperature ?? deviceInfo?.last_temperature ?? null;
  const humi = realtimeData?.humidity ?? deviceInfo?.last_humidity ?? null;
  const soil = realtimeData?.soil_moisture ?? deviceInfo?.last_soil_moisture ?? null;
  const pumpOn = realtimeData?.pump_status ?? deviceInfo?.pump_status ?? false;

  return (
    <ScrollView
      style={styles.container}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} />}>
      {/* 设备状态栏 */}
      <View style={styles.statusBar}>
        <View style={[styles.onlineDot, deviceInfo?.is_online ? styles.online : styles.offline]} />
        <Text style={styles.statusText}>
          {deviceInfo?.is_online ? '设备在线' : '设备离线'}
        </Text>
        {deviceInfo?.wifi_signal && (
          <Text style={styles.wifiText}>WiFi: {deviceInfo.wifi_signal}dBm</Text>
        )}
      </View>

      {/* 传感器数据卡片 */}
      <View style={styles.sensorGrid}>
        <SensorCard
          label="温度"
          value={temp}
          unit="°C"
          icon="🌡️"
          color="#FF6B35"
          warningMax={35}
          warningMin={5}
        />
        <SensorCard
          label="空气湿度"
          value={humi}
          unit="%"
          icon="💨"
          color="#4ECDC4"
          warningMin={30}
        />
        <SensorCard
          label="土壤湿度"
          value={soil}
          unit="%"
          icon="🌱"
          color="#45B7D1"
          warningMin={20}
        />
      </View>

      {/* 水泵控制 */}
      <PumpControl isOn={pumpOn} loading={pumpLoading} onToggle={handlePumpToggle} />

      {/* 固件版本 */}
      {deviceInfo && (
        <Text style={styles.version}>固件版本: v{deviceInfo.firmware_version}</Text>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#F5F5F5'},
  statusBar: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    padding: 12,
    marginBottom: 8,
  },
  onlineDot: {width: 10, height: 10, borderRadius: 5, marginRight: 8},
  online: {backgroundColor: '#4CAF50'},
  offline: {backgroundColor: '#F44336'},
  statusText: {fontSize: 14, color: '#333'},
  wifiText: {marginLeft: 'auto', fontSize: 12, color: '#888'},
  sensorGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'space-between',
    padding: 12,
  },
  sensorCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    alignItems: 'center',
    width: '31%',
    marginBottom: 12,
    elevation: 2,
    shadowColor: '#000',
    shadowOpacity: 0.08,
    shadowRadius: 8,
  },
  sensorCardWarning: {borderWidth: 1.5, borderColor: '#FF4444'},
  sensorIcon: {fontSize: 28, marginBottom: 8},
  sensorValue: {fontSize: 28, fontWeight: 'bold'},
  sensorUnit: {fontSize: 12, color: '#888'},
  sensorLabel: {fontSize: 12, color: '#555', marginTop: 4},
  warningDot: {position: 'absolute', top: 8, right: 8, fontSize: 12},
  pumpCard: {
    backgroundColor: '#fff',
    margin: 12,
    borderRadius: 16,
    padding: 16,
    elevation: 2,
  },
  pumpHeader: {flexDirection: 'row', alignItems: 'center', marginBottom: 16},
  pumpTitle: {fontSize: 16, fontWeight: 'bold', flex: 1},
  pumpStatus: {paddingHorizontal: 12, paddingVertical: 4, borderRadius: 20},
  pumpOn: {backgroundColor: '#4CAF5020'},
  pumpOff: {backgroundColor: '#F4433620'},
  pumpStatusText: {fontSize: 12},
  pumpButtons: {flexDirection: 'row', gap: 12},
  pumpBtn: {
    flex: 1,
    paddingVertical: 14,
    borderRadius: 12,
    alignItems: 'center',
  },
  pumpBtnOn: {backgroundColor: '#4CAF50'},
  pumpBtnOff: {backgroundColor: '#F44336'},
  pumpBtnDisabled: {opacity: 0.4},
  pumpBtnText: {color: '#fff', fontWeight: 'bold', fontSize: 15},
  version: {textAlign: 'center', color: '#bbb', fontSize: 11, marginBottom: 20},
});
