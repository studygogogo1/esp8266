#ifndef PUMP_CONTROLLER_H
#define PUMP_CONTROLLER_H

#include "config.h"

// ==================== 水泵状态变量 ====================
static bool _pumpIsOn = false;
static unsigned long _pumpStartTime = 0;
static int  _pumpDuration = 0;      // 计划运行时长（秒）

// ==================== 初始化水泵 ====================
inline void pumpBegin() {
    pinMode(PUMP_PIN, OUTPUT);
    // 默认关闭水泵（继电器高电平 = 断开）
    digitalWrite(PUMP_PIN, HIGH);
    _pumpIsOn = false;
    Serial.println("[Pump] 水泵初始化完成 (默认关闭)");
}

// ==================== 开启水泵 ====================
// duration: 运行时长（秒），到时间自动关闭（安全机制）
inline void pumpOn(int duration) {
    if (_pumpIsOn) {
        Serial.println("[Pump] 水泵已经在运行中");
        return;
    }

    // 限制最大运行时间
    _pumpDuration = (duration > 0 && duration <= 60) ? duration : 30;
    _pumpStartTime = millis();

    // 低电平触发继电器吸合
    digitalWrite(PUMP_PIN, LOW);
    _pumpIsOn = true;

    Serial.print("[Pump] 水泵开启，计划运行 ");
    Serial.print(_pumpDuration);
    Serial.println(" 秒");
}

// ==================== 关闭水泵 ====================
inline void pumpOff() {
    if (!_pumpIsOn) {
        Serial.println("[Pump] 水泵已经是关闭状态");
        return;
    }

    // 高电平 = 继电器断开
    digitalWrite(PUMP_PIN, HIGH);
    _pumpIsOn = false;
    _pumpStartTime = 0;

    Serial.println("[Pump] 水泵已关闭");
}

// ==================== 检查水泵超时（在 loop 中调用） ====================
// 超过设定时间或超过 PUMP_MAX_RUNTIME 强制关闭
inline void pumpCheckTimeout(unsigned long now) {
    if (!_pumpIsOn) return;

    unsigned long elapsed = now - _pumpStartTime;
    unsigned long maxMs = (unsigned long)_pumpDuration * 1000UL;

    if (elapsed >= maxMs || elapsed >= PUMP_MAX_RUNTIME) {
        Serial.print("[Pump] 超时自动关闭! 已运行 ");
        Serial.print(elapsed / 1000);
        Serial.println(" 秒");
        pumpOff();
    }
}

// ==================== 获取水泵状态 ====================
inline bool pumpIsOn() {
    return _pumpIsOn;
}

#endif // PUMP_CONTROLLER_H
