import os
import sys
import json
import time
import signal
import random
import argparse
from typing import Dict, Any
from collections import Counter

import paho.mqtt.client as mqtt
import pandas as pd
import matplotlib.pyplot as plt

# -----------------------------
# 기본 설정 (환경변수/인자 모두 지원)
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Drone Telemetry MQTT Publisher + QoS 통계")
    p.add_argument("--host", default=os.environ.get("MQTT_HOST", "test.mosquitto.org"))
    p.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    p.add_argument("--tls", action="store_true", default=os.environ.get("MQTT_TLS", "0") == "1")
    p.add_argument("--transport", choices=["tcp", "websockets"], default=os.environ.get("MQTT_TRANSPORT", "tcp"))
    p.add_argument("--fleet", default=os.environ.get("DRONE_FLEET", "lab"))
    p.add_argument("--drone-id", default=os.environ.get("DRONE_ID", "001"))
    p.add_argument("--rate", type=float, default=float(os.environ.get("PUB_RATE_HZ", "5")))
    p.add_argument("--qos", type=int, choices=[0, 1], default=int(os.environ.get("PUB_QOS", "0")))
    p.add_argument("--retain-battery", action="store_true", default=os.environ.get("RETAIN_BATTERY", "0") == "1")
    return p.parse_args()

# -----------------------------
# 토픽 유틸
# -----------------------------
def topic_base(fleet: str, drone_id: str) -> str:
    return f"drone/{fleet}/{drone_id}"

def topics(fleet: str, drone_id: str) -> Dict[str, str]:
    base = topic_base(fleet, drone_id)
    return {
        "gps":      f"{base}/telemetry/gps",
        "alt":      f"{base}/telemetry/alt",
        "battery":  f"{base}/status/battery",
        "online":   f"{base}/status/online",
        "mode":     f"{base}/status/mode",
    }

# -----------------------------
# 상태/시뮬레이션
# -----------------------------
def init_state(drone_id: str) -> Dict[str, Any]:
    return {
        "id": "2022108129",
        "lat": 37.5665,
        "lon": 126.9780,
        "alt": 80.0,
        "spd": 7.5,
        "hdg": 270,
        "bat": 100.0,
        "fix": True,
        "ts": time.time()
    }

def step_state(state: Dict[str, Any]) -> Dict[str, Any]:
    state["lat"] += (random.random() - 0.5) * 0.00008
    state["lon"] += (random.random() - 0.5) * 0.00008
    state["alt"] = max(0.0, state["alt"] + (random.random() - 0.5) * 0.7)
    state["spd"] = max(0.0, state["spd"] + (random.random() - 0.5) * 0.2)
    state["hdg"] = (state["hdg"] + random.choice([-2, -1, 0, 1, 2])) % 360
    state["bat"] = max(0.0, state["bat"] - 0.03)
    state["ts"] = time.time()
    return state

# -----------------------------
# MQTT 클라이언트 생성/콜백
# -----------------------------
def build_client(transport="tcp", use_tls=False) -> mqtt.Client:
    client = mqtt.Client(protocol=mqtt.MQTTv5, transport=transport)
    if use_tls:
        client.tls_set()
    return client

def set_callbacks(client: mqtt.Client):
    def on_connect(c, u, flags, rc, props=None):
        print(f"[CONNECT] rc={rc}")
    def on_disconnect(c, u, rc, props=None):
        print(f"[DISCONNECT] rc={rc}")
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

def set_lwt(client: mqtt.Client, will_topic: str):
    client.will_set(will_topic, payload="offline", qos=1, retain=True)

def publish_json(client: mqtt.Client, topic: str, payload_obj: Dict[str, Any], qos: int, retain: bool):
    payload = json.dumps(payload_obj, ensure_ascii=False)
    result = client.publish(topic, payload, qos=qos, retain=retain)
    result.wait_for_publish()
    return result.rc

# -----------------------------
# Subscriber/통계
# -----------------------------
received_data = []
# 전송 시각을 저장하는 맵
sent_ts_map = {}

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload)
        # 수신 시각과 함께 메시지 ID를 저장
        received_data.append({"id": payload["id"], "ts": time.time()})
    except Exception as e:
        print("[SUB ERROR]", e)

def analyze_stats(total_msgs, received_data):
    # 'received_data'에서 'id'만 추출하여 'received_ids'를 만듦
    received_ids = [d["id"] for d in received_data]
    
    recv_count = Counter(received_ids)
    sent_ids = list(range(total_msgs))
    missing_ids = [i for i in sent_ids if i not in recv_count]
    duplicates_info = {id: count for id, count in recv_count.items() if count > 1}
    duplicates = sum([c-1 for c in duplicates_info.values()])
    
    print("===== 통계 =====")
    print(f"총 발행: {total_msgs}")
    print(f"총 수신: {len(received_ids)}")
    print(f"누락: {len(missing_ids)}")
    print(f"중복: {duplicates}")
    if duplicates > 0:
        print(f"중복된 메시지 id: {duplicates_info}")
        
    latency_data = []
    for d in received_data:
        # 전역 변수인 sent_ts_map에서 전송 시각을 가져옴
        sent_ts = sent_ts_map.get(d["id"])
        if sent_ts:
            # Latency = 수신 시각 - 전송 시각
            latency_data.append(d["ts"] - sent_ts)
            
    if latency_data:
        avg_latency = sum(latency_data) / len(latency_data)
        min_latency = min(latency_data)
        max_latency = max(latency_data)
        print(f"평균 Latency: {avg_latency:.4f}초")
        print(f"최소 Latency: {min_latency:.4f}초")
        print(f"최대 Latency: {max_latency:.4f}초")
        
    # 그래프
    df = pd.DataFrame({
        "msg_id": sent_ids,
        "recv_count": [recv_count.get(i,0) for i in sent_ids]
    })
    plt.figure(figsize=(12,4))
    plt.plot(df["msg_id"], df["recv_count"], label="수신 횟수")
    plt.scatter(df["msg_id"][df["recv_count"]==0], [0]*len(df[df["recv_count"]==0]), color="red", label="누락")
    plt.xlabel("Message ID")
    plt.ylabel("수신 횟수")
    plt.title("QoS{} 메시지 누락/중복".format(args.qos))
    plt.legend()
    plt.show()

# -----------------------------
# 메인 루프
# -----------------------------
def main():
    global args
    args = parse_args()
    args.seconds = 600  # 10분 고정
    t = topics(args.fleet, args.drone_id)

    # Publisher
    client_pub = build_client(transport=args.transport, use_tls=args.tls)
    set_callbacks(client_pub)
    set_lwt(client_pub, t["online"])
    client_pub.connect(args.host, args.port)
    client_pub.loop_start()

    # Subscriber (같은 토픽 구독)
    client_sub = build_client(transport=args.transport, use_tls=args.tls)
    client_sub.on_message = on_message
    client_sub.connect(args.host, args.port)
    client_sub.subscribe(t["gps"], qos=args.qos)
    client_sub.loop_start()

    # 초기 online/모드 발행
    publish_json(client_pub, t["online"], {"status":"online"}, qos=1, retain=True)
    publish_json(client_pub, t["mode"], {"mode":"CRUISE"}, qos=1, retain=True)

    stop = {"flag": False}
    def handle_sig(*_):
        stop["flag"] = True
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    state = init_state(args.drone_id)
    dt = 1.0 / max(0.1, args.rate)
    msg_id = 0

    start_time = time.time()
    try:
        while not stop["flag"] and (time.time() - start_time) < args.seconds:
            state = step_state(state)
            gps_payload = {
                "id": msg_id,
                "lat": state["lat"],
                "lon": state["lon"],
                "spd": state["spd"],
                "hdg": state["hdg"],
                "fix": state["fix"],
                # 메시지 전송 시각을 payload에 추가
                "ts": time.time() 
            }
            # 전역 맵에 메시지 ID와 전송 시각을 저장
            sent_ts_map[msg_id] = gps_payload["ts"]
            
            publish_json(client_pub, t["gps"], gps_payload, qos=args.qos, retain=False)
            msg_id += 1
            time.sleep(dt)
    finally:
        client_pub.loop_stop()
        client_pub.disconnect()
        client_sub.loop_stop()
        client_sub.disconnect()
        # 'received_data'를 analyze_stats 함수에 전달
        analyze_stats(msg_id, received_data)

if __name__ == "__main__":
    main()
