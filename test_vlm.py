import cv2
import torch
import time
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

# 1. 모델 로드 (M1/M2/M3 Apple Silicon 최적화)
model_id = "Qwen/Qwen2-VL-2B-Instruct"
device = "mps" if torch.backends.mps.is_available() else "cpu"
print(f"🚀 [System] {device.upper()} 가속 모드로 로딩 중...")

# M1에서는 4-bit 양자화보다 bfloat16 + MPS 조합이 훨씬 안정적이고 빠릅니다.
model = Qwen2VLForConditionalGeneration.from_pretrained(
    model_id,
    torch_dtype=torch.bfloat16, 
    low_cpu_mem_usage=True,
    device_map={"": device}
)
processor = AutoProcessor.from_pretrained(model_id)

# 2. 실시간 카메라 루프
cap = cv2.VideoCapture(0)
print(f"✅ M1 최적화 준비 완료! (Device: {device})")
print("'s'를 눌러 분석, 'q'를 눌러 종료하세요.")

while True:
    ret, frame = cap.read()
    if not ret: break

    cv2.imshow('VLM Demo (MacBook Pro M1)', frame)

    if cv2.waitKey(1) & 0xFF == ord('s'):
        start_time = time.time()
        print("\n📸 [VLM] M1 Neural Engine/GPU 추론 시작...")
        
        # 해상도 최적화 (M1은 448 정도로 키워도 충분히 빠릅니다)
        resized_frame = cv2.resize(frame, (448, 448))
        pil_img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": pil_img},
                    {"type": "text", "text": "JSON:{count:num, activity:str, clothes:str}"}
                ],
            }
        ]

        # 추론 수행
        text = processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)
        inputs = processor(text=[text], images=image_inputs, padding=True, return_tensors="pt").to(device)

        generated_ids = model.generate(**inputs, max_new_tokens=50)
        output_text = processor.batch_decode(generated_ids, skip_special_tokens=True)
        
        print("-" * 40)
        print(f"⏱️ 소요 시간: {time.time() - start_time:.2f}초")
        print(f"🔍 [분석 결과]: {output_text[0].split('assistant')[-1].strip()}")
        print("-" * 40)

    if cv2.waitKey(1) & 0xFF == ord('q'): break

cap.release()
cv2.destroyAllWindows()