import cv2
import torch
import time
import json
import re
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# 1. 모델 및 프로세서 로드 (Apple Silicon MPS 가속)
model_id = "Qwen/Qwen2-VL-2B-Instruct"
device = "mps" if torch.backends.mps.is_available() else "cpu"

print(f"🚀 [System] {device.upper()} 가속 모드로 모델을 로드 중입니다...")

model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16, 
    low_cpu_mem_usage=True,
    device_map={"": device}
)
processor = AutoProcessor.from_pretrained(model_id)

# 2. 카메라 설정
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("❌ 카메를 열 수 없습니다.")
    exit()

print(f"✅ 환경 준비 완료! (Device: {device})")
print("-" * 50)
print(" 지시사항:")
print(" 1. 's' 키를 누르면 현재 화면을 분석합니다.")
print(" 2. 'q' 키를 누르면 프로그램을 종료합니다.")
print("-" * 50)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # 실시간 화면 표시
    cv2.imshow('HVAC VLM Control System (MacBook)', frame)

    key = cv2.waitKey(1) & 0xFF

    # 's' 키를 눌러 추론 시작
    if key == ord('s'):
        start_time = time.time()
        print("\n📸 [VLM] 분석을 시작합니다...")

        # [경량화 1] 해상도 축소 (224x224는 속도와 정확도의 타협점)
        input_size = 224
        resized_frame = cv2.resize(frame, (input_size, input_size))
        pil_img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))

        # [경량화 2] 엄격한 JSON 출력 프롬프트
        # 모델이 딴소리하지 못하도록 예시(Example)를 포함합니다.
        prompt_text = (
            "Analyze the image and return ONLY a JSON object. "
            "Fields: {'sleeves': 'long'|'short', 'outerwear': 'yes'|'no', 'window': 'open'|'closed', 'room_size': 'small'|'medium'|'large'}. "
            "Example: {\"sleeves\": \"short\", \"outerwear\": \"no\", \"window\": \"closed\", \"room_size\": \"small\"}"
        )

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {"type": "text", "text": prompt_text}
                ],
            }
        ]

        # 데이터 전처리
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, padding=True, return_tensors="pt").to(device)

        # [경량화 3] 추론 파라미터 최적화
        # max_new_tokens를 줄여서 생성을 일찍 끝내게 합니다.
        generated_ids = model.generate(
            **inputs, 
            max_new_tokens=40, 
            do_sample=False  # 일관된 결과를 위해 그리디 서치 사용
        )
        
        # 결과 디코딩
        output_text = processor.batch_decode(generated_ids, skip_special_tokens=True)
        # 'assistant' 이후의 내용만 추출
        raw_response = output_text[0].split('assistant')[-1].strip()

        # [추가] JSON 파싱 및 데이터 활용 로직
        print("-" * 40)
        try:
            # 문자열에서 JSON 형태만 찾아내기 (간혹 모델이 앞뒤에 설명을 붙일 경우 대비)
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                final_json = json.loads(json_match.group())
                
                # 결과 출력
                print(f"⏱️ 추론 소요 시간: {time.time() - start_time:.2f}초")
                print(f"👕 소매 상태: {final_json.get('sleeves')}")
                print(f"🧥 외투 착용: {final_json.get('outerwear')}")
                print(f"🪟 창문 상태: {final_json.get('window')}")
                print(f"🏠 방 크기: {final_json.get('room_size')}")
                
                # --- 여기에 에어컨 제어 로직을 추가하면 됩니다 ---
                # if final_json.get('sleeves') == 'short':
                #     send_command_to_ac("set_temp_24")
                # ------------------------------------------
            else:
                print(f"⚠️ JSON 형식을 찾을 수 없음: {raw_response}")
        except Exception as e:
            print(f"❌ 파싱 에러: {e}")
            print(f"원본 응답: {raw_response}")
        print("-" * 40)

    # 'q' 키를 눌러 종료
    elif key == ord('q'):
        print("\n👋 프로그램을 종료합니다.")
        break

cap.release()
cv2.destroyAllWindows()