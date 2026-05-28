/**
 * 水泵操作记录页面
 */
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  FlatList,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import {pumpApi} from '../api';
import {DEFAULT_DEVICE_ID} from '../config';

const SOURCE_LABELS: Record<string, string> = {
  app: '手动（App）',
  auto: '自动规则',
  device: '设备本地',
};

export default function PumpLogsScreen() {
  const [logs, setLogs] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const deviceId = DEFAULT_DEVICE_ID;

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    setLoading(true);
    try {
      const resp = await pumpApi.getLogs(deviceId, 7);
      setLogs(resp.data.logs);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const renderItem = ({item}: {item: any}) => (
    <View style={styles.logItem}>
      <View style={[styles.actionBadge, item.action === 'on' ? styles.badgeOn : styles.badgeOff]}>
        <Text style={styles.actionText}>{item.action === 'on' ? '开启' : '关闭'}</Text>
      </View>
      <View style={styles.logInfo}>
        <Text style={styles.logSource}>{SOURCE_LABELS[item.source] ?? item.source}</Text>
        {item.duration && item.action === 'on' && (
          <Text style={styles.logDuration}>持续 {item.duration} 秒</Text>
        )}
      </View>
      <Text style={styles.logTime}>
        {new Date(item.time).toLocaleString('zh-CN', {
          month: '2-digit',
          day: '2-digit',
          hour: '2-digit',
          minute: '2-digit',
        })}
      </Text>
    </View>
  );

  return (
    <FlatList
      style={styles.container}
      data={logs}
      keyExtractor={item => String(item.id)}
      renderItem={renderItem}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={loadLogs} />}
      ListEmptyComponent={
        loading ? (
          <ActivityIndicator style={{marginTop: 40}} />
        ) : (
          <Text style={styles.emptyText}>暂无记录</Text>
        )
      }
      ListHeaderComponent={
        <Text style={styles.header}>最近 7 天水泵操作记录（共 {logs.length} 条）</Text>
      }
    />
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#F5F5F5'},
  header: {padding: 16, color: '#888', fontSize: 13},
  logItem: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    marginHorizontal: 12,
    marginBottom: 6,
    borderRadius: 10,
    padding: 12,
  },
  actionBadge: {
    width: 48,
    height: 48,
    borderRadius: 24,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: 12,
  },
  badgeOn: {backgroundColor: '#4CAF5020'},
  badgeOff: {backgroundColor: '#F4433620'},
  actionText: {fontSize: 13, fontWeight: 'bold'},
  logInfo: {flex: 1},
  logSource: {fontSize: 14, color: '#333'},
  logDuration: {fontSize: 12, color: '#888', marginTop: 2},
  logTime: {fontSize: 12, color: '#aaa'},
  emptyText: {textAlign: 'center', color: '#bbb', marginTop: 60},
});
