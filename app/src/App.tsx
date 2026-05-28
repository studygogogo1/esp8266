/**
 * App 主路由入口
 */
import React, {useEffect} from 'react';
import {NavigationContainer} from '@react-navigation/native';
import {createBottomTabNavigator} from '@react-navigation/bottom-tabs';
import {Text} from 'react-native';

import DashboardScreen from './screens/DashboardScreen';
import HistoryScreen from './screens/HistoryScreen';
import AlertsScreen from './screens/AlertsScreen';
import PumpLogsScreen from './screens/PumpLogsScreen';
import {wsClient} from './api/websocket';
import {useDeviceStore} from './store/deviceStore';
import {DEFAULT_DEVICE_ID} from './config';

const Tab = createBottomTabNavigator();

const tabIcons: Record<string, string> = {
  仪表盘: '🏠',
  历史曲线: '📈',
  告警设置: '🔔',
  浇水记录: '💧',
};

export default function App() {
  const {setCurrentDeviceId, unreadAlerts} = useDeviceStore();

  useEffect(() => {
    // 初始化设备 ID
    setCurrentDeviceId(DEFAULT_DEVICE_ID);
    // 连接 WebSocket 实时数据
    wsClient.connect();
    return () => wsClient.disconnect();
  }, []);

  return (
    <NavigationContainer>
      <Tab.Navigator
        screenOptions={({route}) => ({
          tabBarIcon: () => (
            <Text style={{fontSize: 20}}>{tabIcons[route.name] ?? '📱'}</Text>
          ),
          tabBarActiveTintColor: '#4ECDC4',
          tabBarInactiveTintColor: '#888',
          headerStyle: {backgroundColor: '#4ECDC4'},
          headerTintColor: '#fff',
          headerTitleStyle: {fontWeight: 'bold'},
        })}>
        <Tab.Screen name="仪表盘" component={DashboardScreen} />
        <Tab.Screen name="历史曲线" component={HistoryScreen} />
        <Tab.Screen
          name="告警设置"
          component={AlertsScreen}
          options={{
            tabBarBadge: unreadAlerts.length > 0 ? unreadAlerts.length : undefined,
          }}
        />
        <Tab.Screen name="浇水记录" component={PumpLogsScreen} />
      </Tab.Navigator>
    </NavigationContainer>
  );
}
