import os
import sys
import json
import time
import signal
import random
import argparse
import csv
from typing import Dict, Any
from collections import Counter
import paho.mqtt.client as mqtt
import glob
import pandas as pd

# -----------------------------
# CSV / JSONL 저장 로직
# -----------------------------
current_csv = None
current_jsonl = None
current_start_minute = None
SAVE_DIR = "/Users/wskang/Desktop/IOT기초/실습/data"
os.makedirs(SAVE_DIR, exist_ok=True)

def open_new_files():
    global current_csv, current_jsonl, current_start_minute
    ts = time.strftime("%Y%m%d_%H%M")
    csv_name = os.path.join(SAVE_DIR, f"pub_telemetry_{ts}.csv")
    jsonl_name = os.path.join(SAVE_DIR, f"pub_telemetry_{ts}.jsonl")

    current_csv = open(csv_name, "w", newline="", encoding="utf-8")
    writer = csv.writer(current_csv)
    writer.writerow(["id", "lat", "lon", "alt", "spd", "hdg", "bat", "fix", "ts"])
    current_jsonl = open(jsonl_name, "w", encoding="utf-8")

    # 5분 단위 시작 시간 저장
    current_start_minute = int(time.time() //(60 * 5))

def save_data(state):
    global current_csv, current_jsonl, current_start_minute
    now_minute = int(time.time() // (60*5))

    # 5분 단위 회전 체크
    if current_csv is None or now_minute != current_start_minute:
        if current_csv:
            current_csv.close()
            current_jsonl.close()
        open_new_files()

    # 배터리 값 검증
    if not (0 <= state["bat"] <= 100):
        print(f"[WARN] invalid battery={state['bat']}, skip save")
        return

    # CSV 저장
    writer = csv.writer(current_csv)
    writer.writerow([state["id"], state["lat"], state["lon"], state["alt"],
                     state["spd"], state["hdg"], state["bat"], state["fix"], state["ts"]])
    current_csv.flush()

    # JSONL 저장
    current_jsonl.write(json.dumps(state, ensure_ascii=False) + "\n")
    current_jsonl.flush()

# -----------------------------
# 평균 배터리 계산 & 저전력 데이터 추출
# -----------------------------
def analyze_battery_data():
    files = glob.glob(os.path.join(SAVE_DIR, "pub_telemetry_*.csv"))
    if not files:
        print("[WARN] CSV 파일이 없습니다.")
        return

    df = pd.concat([pd.read_csv(f) for f in files])
    print(f"\n===== 배터리 데이터 분석 =====")
    print(f"평균 배터리: {df['bat'].mean():.2f}%")
    low_bat_df = df[df['bat'] < 20]
    print(f"저전력 데이터 개수: {len(low_bat_df)}")
    print(low_bat_df.head())
    print("================================\n")

# -----------------------------
# 기본 설정
# -----------------------------
def parse_args():
    p = argparse.ArgumentParser(description="Drone Telemetry MQTT Publisher + CSV/JSONL 저장")
    p.add_argument("--host", default=os.environ.get("MQTT_HOST", "test.mosquitto.org"))
    p.add_argument("--port", type=int, default=int(os.environ.get("MQTT_PORT", "1883")))
    p.add_argument("--tls", action="store_true", default=os.environ.get("MQTT_TLS", "0") == "1")
    p.add_argument("--transport", choices=["tcp", "websockets"], default=os.environ.get("MQTT_TRANSPORT", "tcp"))
    p.add_argument("--fleet", default=os.environ.get("DRONE_FLEET", "lab"))
    p.add_argument("--drone-id", default=os.environ.get("DRONE_ID", "2022108129"))  # 학번 변경 가능
    p.add_argument("--rate", type=float, default=float(os.environ.get("PUB_RATE_HZ", "5")))
    p.add_argument("--qos", type=int, choices=[0, 1], default=int(os.environ.get("PUB_QOS", "0")))
    return p.parse_args()

# -----------------------------
# 토픽
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
# 상태 생성/변경
# -----------------------------
def init_state(drone_id: str) -> Dict[str, Any]:
    return {
        "id": drone_id,
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
# MQTT
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
# 메인 루프
# -----------------------------
def main():
    global args
    args = parse_args()
    args.seconds = 600  # 최소 10분 실행
    t = topics(args.fleet, args.drone_id)

    client_pub = build_client(transport=args.transport, use_tls=args.tls)
    set_callbacks(client_pub)
    set_lwt(client_pub, t["online"])
    client_pub.connect(args.host, args.port)
    client_pub.loop_start()

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
    open_new_files()
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
                "ts": time.time()
            }

            publish_json(client_pub, t["gps"], gps_payload, qos=args.qos, retain=False)
            save_data(state)  # 저장 로직 호출

            msg_id += 1
            time.sleep(dt)

    finally:
        client_pub.loop_stop()
        client_pub.disconnect()
        if current_csv:
            current_csv.close()
        if current_jsonl:
            current_jsonl.close()
        analyze_battery_data()

if __name__ == "__main__":
    main()
