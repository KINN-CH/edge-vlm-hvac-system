import torch
import json
import re
import cv2
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info

class VLMProcessor:
    def __init__(self):
        # 1. 디바이스 설정 (현재 라이젠 노트북은 'cpu', 맥북은 'mps'로 변경 예정)
        # self.device = "mps"  <-- 나중에 맥북 오면 이거 주석 해제하세요!
        self.device = "cpu"    # 현재 윈도우 라이젠 노트북용
        
        print(f"🚀 [VLM] 현재 {self.device.upper()} 모드로 초기화 중...")
        
        self.model_id = "Qwen/Qwen2-VL-2B-Instruct"
        
        try:
            # CPU 환경에서는 메모리 효율을 위해 float32를 사용합니다.
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_id,
                torch_dtype=torch.float32 if self.device == "cpu" else torch.bfloat16,
                low_cpu_mem_usage=True,
                device_map={"": self.device}
            )
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            print(f"✅ [VLM] {self.device.upper()} 로드 완료")
        except Exception as e:
            print(f"❌ [VLM] 로드 에러: {e}")

    def analyze_frame(self, frame):
        # [윈도우 라이젠 최적화] CPU 부하를 줄이기 위해 해상도를 낮춥니다.
        # 맥북으로 바꾸면 448 정도로 높여도 됩니다.
        input_size = 160 
        resized_frame = cv2.resize(frame, (input_size, input_size))
        pil_img = Image.fromarray(cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB))

        # 프롬프트: 답변이 길어질수록 CPU 연산 시간이 기하급수적으로 늘어납니다.
        prompt_text = (
            "Analyze and return ONLY JSON: {'sleeves': 'long'|'short', 'outerwear': 'yes'|'no', "
            "'activity': 'sitting'|'walking'|'cooking', 'people': num}"
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

        # 전처리 및 추론
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)
        inputs = self.processor(text=[text], images=image_inputs, padding=True, return_tensors="pt").to(self.device)

        with torch.no_grad():
            # CPU에서는 max_new_tokens가 적을수록 생명입니다.
            generated_ids = self.model.generate(**inputs, max_new_tokens=40, do_sample=False)
            
        output_text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        raw_response = output_text[0].split('assistant')[-1].strip()

        try:
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                
                # PMV 변수 매핑 (ISO 7730 근거)
                clo = 0.5 if data.get('sleeves') == 'short' else 1.0
                if data.get('outerwear') == 'yes': clo += 0.3
                
                activity_map = {'sitting': 1.0, 'walking': 1.5, 'cooking': 2.0}
                met = activity_map.get(data.get('activity'), 1.2)
                
                return {"clo": clo, "met": met, "count": data.get('people', 1)}
        except:
            pass
            
        return None