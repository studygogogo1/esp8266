/**
 * 告警与自动规则配置页面
 */
import React, {useEffect, useState} from 'react';
import {
  View,
  Text,
  StyleSheet,
  ScrollView,
  Switch,
  TouchableOpacity,
  Alert,
  TextInput,
  Modal,
  ActivityIndicator,
} from 'react-native';
import {alertApi, ruleApi} from '../api';
import {DEFAULT_DEVICE_ID} from '../config';

const ALERT_RULE_TYPES = [
  {key: 'temp_high', label: '温度过高', unit: '°C', defaultThreshold: 35},
  {key: 'temp_low', label: '温度过低', unit: '°C', defaultThreshold: 5},
  {key: 'humidity_low', label: '空气湿度过低', unit: '%', defaultThreshold: 30},
  {key: 'soil_dry', label: '土壤过干', unit: '%', defaultThreshold: 20},
];

export default function AlertsScreen() {
  const [alertRules, setAlertRules] = useState<any[]>([]);
  const [autoRules, setAutoRules] = useState<any[]>([]);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const [showAddModal, setShowAddModal] = useState(false);
  const [editThreshold, setEditThreshold] = useState('');
  const [editRuleType, setEditRuleType] = useState('');

  const deviceId = DEFAULT_DEVICE_ID;

  useEffect(() => {
    loadAll();
  }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [alertRulesResp, autoRulesResp, alertsResp] = await Promise.all([
        alertApi.getRules(deviceId),
        ruleApi.getRules(deviceId),
        alertApi.getAlerts(deviceId, 3),
      ]);
      setAlertRules(alertRulesResp.data);
      setAutoRules(autoRulesResp.data);
      setAlerts(alertsResp.data.alerts);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggleAlertRule = async (ruleType: string, threshold: number, enabled: boolean) => {
    await alertApi.upsertRule(deviceId, ruleType, threshold, enabled);
    loadAll();
  };

  const handleSaveThreshold = async () => {
    const val = parseFloat(editThreshold);
    if (isNaN(val)) {
      Alert.alert('请输入有效数字');
      return;
    }
    await alertApi.upsertRule(deviceId, editRuleType, val, true);
    setShowAddModal(false);
    loadAll();
  };

  const handleDeleteAutoRule = (ruleId: number) => {
    Alert.alert('确认', '删除这条自动规则?', [
      {text: '取消'},
      {
        text: '删除',
        style: 'destructive',
        onPress: async () => {
          await ruleApi.deleteRule(deviceId, ruleId);
          loadAll();
        },
      },
    ]);
  };

  return (
    <ScrollView style={styles.container}>
      {/* 告警规则配置 */}
      <Text style={styles.sectionTitle}>告警规则</Text>
      {ALERT_RULE_TYPES.map(type => {
        const rule = alertRules.find((r: any) => r.rule_type === type.key);
        const enabled = rule?.enabled ?? false;
        const threshold = rule?.threshold ?? type.defaultThreshold;

        return (
          <View key={type.key} style={styles.ruleCard}>
            <View style={styles.ruleLeft}>
              <Text style={styles.ruleName}>{type.label}</Text>
              <TouchableOpacity
                onPress={() => {
                  setEditRuleType(type.key);
                  setEditThreshold(String(threshold));
                  setShowAddModal(true);
                }}>
                <Text style={styles.ruleThreshold}>
                  阈值: {threshold}{type.unit}
                  <Text style={styles.editHint}> 点击修改</Text>
                </Text>
              </TouchableOpacity>
            </View>
            <Switch
              value={enabled}
              onValueChange={val => handleToggleAlertRule(type.key, threshold, val)}
              trackColor={{true: '#4ECDC4'}}
            />
          </View>
        );
      })}

      {/* 自动控制规则 */}
      <Text style={styles.sectionTitle}>自动控制规则</Text>
      {autoRules.length === 0 ? (
        <Text style={styles.emptyText}>暂无规则，可在此设置土壤过干自动浇水等规则</Text>
      ) : (
        autoRules.map((rule: any) => (
          <View key={rule.id} style={styles.ruleCard}>
            <View style={styles.ruleLeft}>
              <Text style={styles.ruleName}>{rule.rule_name}</Text>
              <Text style={styles.ruleDesc}>
                当 {rule.condition} 时，开泵 {rule.action_duration}秒
              </Text>
            </View>
            <TouchableOpacity onPress={() => handleDeleteAutoRule(rule.id)}>
              <Text style={styles.deleteBtn}>🗑️</Text>
            </TouchableOpacity>
          </View>
        ))
      )}

      <TouchableOpacity
        style={styles.addBtn}
        onPress={() => {
          Alert.alert('提示', '自动规则创建功能即将上线');
        }}>
        <Text style={styles.addBtnText}>+ 添加自动规则</Text>
      </TouchableOpacity>

      {/* 最近告警记录 */}
      <Text style={styles.sectionTitle}>最近告警（3天）</Text>
      {alerts.length === 0 ? (
        <Text style={styles.emptyText}>暂无告警记录 ✅</Text>
      ) : (
        alerts.map((a: any) => (
          <View key={a.id} style={[styles.alertItem, !a.is_read && styles.alertUnread]}>
            <Text style={styles.alertMsg}>{a.message}</Text>
            <Text style={styles.alertTime}>
              {new Date(a.time).toLocaleString('zh-CN')}
            </Text>
          </View>
        ))
      )}

      {/* 编辑阈值弹窗 */}
      <Modal visible={showAddModal} transparent animationType="slide">
        <View style={styles.modalOverlay}>
          <View style={styles.modalCard}>
            <Text style={styles.modalTitle}>
              修改阈值 - {ALERT_RULE_TYPES.find(t => t.key === editRuleType)?.label}
            </Text>
            <TextInput
              style={styles.input}
              value={editThreshold}
              onChangeText={setEditThreshold}
              keyboardType="numeric"
              placeholder="输入阈值"
            />
            <View style={styles.modalBtns}>
              <TouchableOpacity
                style={[styles.modalBtn, styles.cancelBtn]}
                onPress={() => setShowAddModal(false)}>
                <Text>取消</Text>
              </TouchableOpacity>
              <TouchableOpacity style={[styles.modalBtn, styles.saveBtn]} onPress={handleSaveThreshold}>
                <Text style={{color: '#fff'}}>保存</Text>
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: {flex: 1, backgroundColor: '#F5F5F5'},
  sectionTitle: {
    fontSize: 15,
    fontWeight: 'bold',
    color: '#333',
    margin: 16,
    marginBottom: 8,
  },
  ruleCard: {
    backgroundColor: '#fff',
    marginHorizontal: 12,
    marginBottom: 8,
    borderRadius: 12,
    padding: 14,
    flexDirection: 'row',
    alignItems: 'center',
    elevation: 1,
  },
  ruleLeft: {flex: 1},
  ruleName: {fontSize: 15, fontWeight: '500', color: '#333'},
  ruleThreshold: {fontSize: 13, color: '#888', marginTop: 4},
  editHint: {fontSize: 11, color: '#4ECDC4'},
  ruleDesc: {fontSize: 12, color: '#888', marginTop: 4},
  deleteBtn: {fontSize: 20, padding: 4},
  addBtn: {
    margin: 12,
    borderWidth: 1.5,
    borderColor: '#4ECDC4',
    borderStyle: 'dashed',
    borderRadius: 12,
    padding: 14,
    alignItems: 'center',
  },
  addBtnText: {color: '#4ECDC4', fontSize: 14},
  emptyText: {textAlign: 'center', color: '#bbb', fontSize: 13, margin: 20},
  alertItem: {
    backgroundColor: '#fff',
    marginHorizontal: 12,
    marginBottom: 6,
    borderRadius: 10,
    padding: 12,
  },
  alertUnread: {borderLeftWidth: 3, borderLeftColor: '#FF4444'},
  alertMsg: {fontSize: 14, color: '#333'},
  alertTime: {fontSize: 11, color: '#bbb', marginTop: 4},
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  modalCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    width: '80%',
  },
  modalTitle: {fontSize: 16, fontWeight: 'bold', marginBottom: 16},
  input: {
    borderWidth: 1,
    borderColor: '#ddd',
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    marginBottom: 16,
  },
  modalBtns: {flexDirection: 'row', gap: 12},
  modalBtn: {flex: 1, padding: 12, borderRadius: 8, alignItems: 'center'},
  cancelBtn: {backgroundColor: '#f5f5f5'},
  saveBtn: {backgroundColor: '#4ECDC4'},
});
