/**
 * 历史数据图表页面
 * 显示温度、湿度、土壤湿度的折线图
 */
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  TouchableOpacity,
  Dimensions,
  ActivityIndicator,
} from 'react-native';
import {LineChart} from 'react-native-chart-kit';
import {sensorApi} from '../api';
import {DEFAULT_DEVICE_ID} from '../config';

const screenWidth = Dimensions.get('window').width;

const TIME_RANGES = [
  {label: '6小时', hours: 6},
  {label: '24小时', hours: 24},
  {label: '3天', hours: 72},
  {label: '7天', hours: 168},
];

const DATA_TYPES = [
  {key: 'temperature', label: '温度', unit: '°C', color: '#FF6B35'},
  {key: 'humidity', label: '空气湿度', unit: '%', color: '#4ECDC4'},
  {key: 'soil_moisture', label: '土壤湿度', unit: '%', color: '#45B7D1'},
];

export default function HistoryScreen() {
  const [loading, setLoading] = useState(false);
  const [selectedHours, setSelectedHours] = useState(24);
  const [selectedType, setSelectedType] = useState('temperature');
  const [chartData, setChartData] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  const deviceId = DEFAULT_DEVICE_ID;

  useEffect(() => {
    loadData();
  }, [selectedHours]);

  const loadData = async () => {
    setLoading(true);
    try {
      const [histResp, statsResp] = await Promise.all([
        sensorApi.getHistory(deviceId, selectedHours),
        sensorApi.getStats(deviceId, selectedHours),
      ]);

      const records = histResp.data.data;
      if (records.length === 0) {
        setChartData(null);
        return;
      }

      // 精简数据点（最多显示 50 个点）
      const step = Math.max(1, Math.floor(records.length / 50));
      const sampled = records.filter((_: any, i: number) => i % step === 0);

      const labels = sampled.map((item: any, i: number) =>
        i % Math.max(1, Math.floor(sampled.length / 6)) === 0
          ? new Date(item.event_time || item.time).toLocaleTimeString('zh-CN', {
              hour: '2-digit',
              minute: '2-digit',
            })
          : '',
      );

      setChartData({
        labels,
        temperature: sampled.map((r: any) => r.temperature ?? 0),
        humidity: sampled.map((r: any) => r.humidity ?? 0),
        soil_moisture: sampled.map((r: any) => r.soil_moisture ?? 0),
      });
      setStats(statsResp.data);
    } catch (e) {
      console.error('加载历史数据失败', e);
    } finally {
      setLoading(false);
    }
  };

  const currentType = DATA_TYPES.find(t => t.key === selectedType)!;

  const chartValues = chartData?.[selectedType] ?? [];

  return (
    <ScrollView style={styles.container}>
      {/* 时间范围选择 */}
      <View style={styles.tabRow}>
        {TIME_RANGES.map(r => (
          <TouchableOpacity
            key={r.hours}
            style={[styles.tab, selectedHours === r.hours && styles.tabActive]}
            onPress={() => setSelectedHours(r.hours)}>
            <Text style={[styles.tabText, selectedHours === r.hours && styles.tabTextActive]}>
              {r.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 数据类型选择 */}
      <View style={styles.typeRow}>
        {DATA_TYPES.map(t => (
          <TouchableOpacity
            key={t.key}
            style={[styles.typeBtn, selectedType === t.key && {backgroundColor: t.color}]}
            onPress={() => setSelectedType(t.key)}>
            <Text style={[styles.typeBtnText, selectedType === t.key && styles.typeBtnTextActive]}>
              {t.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* 图表 */}
      {loading ? (
        <ActivityIndicator style={{marginTop: 40}} size="large" color="#4ECDC4" />
      ) : chartData && chartValues.length > 0 ? (
        <>
          <Text style={styles.chartTitle}>
            {currentType.label}（{currentType.unit}）
          </Text>
          <LineChart
            data={{
              labels: chartData.labels,
              datasets: [{data: chartValues, color: () => currentType.color, strokeWidth: 2}],
            }}
            width={screenWidth - 24}
            height={220}
            chartConfig={{
              backgroundColor: '#fff',
              backgroundGradientFrom: '#fff',
              backgroundGradientTo: '#fff',
              decimalPlaces: 1,
              color: () => currentType.color,
              labelColor: () => '#888',
              propsForDots: {r: '3', fill: currentType.color},
            }}
            bezier
            style={styles.chart}
          />

          {/* 统计信息 */}
          {stats && (
            <View style={styles.statsCard}>
              <Text style={styles.statsTitle}>统计（最近{selectedHours}小时）</Text>
              {selectedType === 'temperature' && stats.temperature && (
                <View style={styles.statsRow}>
                  <StatItem label="平均" value={stats.temperature.avg} unit="°C" />
                  <StatItem label="最高" value={stats.temperature.max} unit="°C" color="#FF4444" />
                  <StatItem label="最低" value={stats.temperature.min} unit="°C" color="#4488FF" />
                </View>
              )}
              {selectedType === 'humidity' && stats.humidity && (
                <View style={styles.statsRow}>
                  <StatItem label="平均湿度" value={stats.humidity.avg} unit="%" />
                </View>
              )}
              {selectedType === 'soil_moisture' && stats.soil_moisture && (
                <View style={styles.statsRow}>
                  <StatItem label="平均土壤湿度" value={stats.soil_moisture.avg} unit="%" />
                </View>
              )}
            </View>
          )}
        </>
      ) : (
        <View style={styles.empty}>
          <Text style={styles.emptyText}>暂无数据</Text>
        </View>
      )}
    </ScrollView>
  );
}

const StatItem = ({
  label,
  value,
  unit,
  color = '#333',
}: {
  label: string;
  value: number | null;
  unit: string;
  color?: string;
}) => (
  <View style={styles.statItem}>
    <Text style={[styles.statValue, {color}]}>{value?.toFixed(1) ?? '--'}</Text>
    <Text style={styles.statUnit}>{unit}</Text>
    <Text style={styles.statLabel}>{label}</Text>
  </View>
);

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#F5F5F5'},
  tabRow: {
    flexDirection: 'row',
    backgroundColor: '#fff',
    padding: 8,
  },
  tab: {
    flex: 1,
    paddingVertical: 8,
    alignItems: 'center',
    borderRadius: 8,
  },
  tabActive: {backgroundColor: '#4ECDC420'},
  tabText: {fontSize: 13, color: '#888'},
  tabTextActive: {color: '#4ECDC4', fontWeight: 'bold'},
  typeRow: {
    flexDirection: 'row',
    padding: 12,
    gap: 8,
  },
  typeBtn: {
    flex: 1,
    paddingVertical: 8,
    borderRadius: 8,
    alignItems: 'center',
    backgroundColor: '#fff',
    elevation: 1,
  },
  typeBtnText: {fontSize: 12, color: '#555'},
  typeBtnTextActive: {color: '#fff', fontWeight: 'bold'},
  chartTitle: {
    textAlign: 'center',
    fontSize: 14,
    color: '#666',
    marginBottom: 4,
  },
  chart: {marginHorizontal: 12, borderRadius: 16},
  statsCard: {
    backgroundColor: '#fff',
    margin: 12,
    borderRadius: 16,
    padding: 16,
    elevation: 2,
  },
  statsTitle: {fontSize: 14, color: '#888', marginBottom: 12},
  statsRow: {flexDirection: 'row'},
  statItem: {flex: 1, alignItems: 'center'},
  statValue: {fontSize: 24, fontWeight: 'bold'},
  statUnit: {fontSize: 11, color: '#888'},
  statLabel: {fontSize: 12, color: '#666', marginTop: 2},
  empty: {flex: 1, alignItems: 'center', justifyContent: 'center', padding: 60},
  emptyText: {color: '#bbb', fontSize: 14},
});
