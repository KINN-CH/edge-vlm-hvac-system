import torch
import json
import re
import cv2
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info


class VLMProcessor:
    """
    [Vision Language Model 처리기]
    모델: Qwen2-VL-2B-Instruct (CPU, Windows 최적화)
    역할: 카메라 프레임에서 착의량(Clo), 대사율(Met), 인원수를 감지해 PMV 입력값으로 변환
    """

    # PMV 입력 매핑 테이블 (ISO 7730:2005 근거)
    CLO_BASE  = {'short': 0.5, 'long': 1.0}
    CLO_OUTER = 0.3   # 아우터 착용 시 추가 착의량

    MET_MAP = {
        'sitting':    1.0,   # 착석 (사무 작업)
        'standing':   1.2,   # 기립 (가벼운 활동)
        'walking':    1.5,   # 보행
        'cooking':    2.0,   # 조리 (서서 작업)
        'exercising': 3.0,   # 운동 (유산소)
    }
    MET_DEFAULT = 1.2  # 분류 불가 시 기립 수준

    def __init__(self):
        self.device   = "cpu"
        self.model_id = "Qwen/Qwen2-VL-2B-Instruct"

        print(f"🚀 [VLM] {self.device.upper()} 모드로 초기화 중...")

        try:
            self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                self.model_id,
                torch_dtype=torch.float32,   # CPU에서는 float32
                low_cpu_mem_usage=True,
                device_map={"": self.device}
            )
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            print(f"✅ [VLM] {self.model_id} 로드 완료")
        except Exception as e:
            print(f"❌ [VLM] 모델 로드 실패: {e}")
            self.model     = None
            self.processor = None

    def analyze_frame(self, frame):
        """
        프레임 분석 → PMV 입력 파라미터 반환

        Returns:
            dict: {'clo': float, 'met': float, 'count': int}
            None: 분석 실패 시
        """
        if self.model is None or self.processor is None:
            print("⚠️ [VLM] 모델이 로드되지 않아 분석 불가.")
            return None

        # [최적화] CPU 부하 감소를 위해 160×160으로 다운스케일
        resized   = cv2.resize(frame, (160, 160))
        pil_img   = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))

        prompt_text = (
            "Analyze this image. Return ONLY a JSON object with these keys: "
            "{'sleeves': 'long'|'short', "
            "'outerwear': 'yes'|'no', "
            "'activity': 'sitting'|'standing'|'walking'|'cooking'|'exercising', "
            "'people': <integer>}"
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_img},
                {"type": "text",  "text": prompt_text},
            ],
        }]

        text          = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)
        inputs        = self.processor(
            text=[text], images=image_inputs, padding=True, return_tensors="pt"
        ).to(self.device)

        with torch.no_grad():
            generated_ids = self.model.generate(**inputs, max_new_tokens=40, do_sample=False)

        output_text  = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        raw_response = output_text[0].split('assistant')[-1].strip()

        return self._parse_response(raw_response)

    def _parse_response(self, raw_response: str):
        """VLM 응답 파싱 및 PMV 파라미터 매핑"""
        try:
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                print(f"⚠️ [VLM] JSON 미발견. 응답: {raw_response[:80]}")
                return None

            data = json.loads(json_match.group())

            clo = self.CLO_BASE.get(data.get('sleeves', 'long'), 1.0)
            if data.get('outerwear') == 'yes':
                clo += self.CLO_OUTER

            met = self.MET_MAP.get(data.get('activity'), self.MET_DEFAULT)

            return {
                "clo":   round(clo, 2),
                "met":   met,
                "count": max(0, int(data.get('people', 1))),
            }

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"⚠️ [VLM] 파싱 실패: {e} | 응답: {raw_response[:80]}")
            return None
