import torch
import json
import re
import platform
import cv2
from PIL import Image
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from qwen_vl_utils import process_vision_info


class VLMProcessor:
    """
    [Vision Language Model 처리기]
    모델: Qwen2-VL-2B-Instruct (디바이스 자동 선택)
    역할: 카메라 프레임에서 PMV 입력 파라미터 및 맥락 신호를 추출합니다.

    ── 디바이스 우선순위 ───────────────────────────────────────────────────────
      1. MPS  (Apple Silicon M1~M5) — float16
      2. CUDA (NVIDIA GPU)          — float16
      3. CPU  (그 외 모든 환경)       — float32

    ── 감지 항목 ──────────────────────────────────────────────────────────────
    PMV 입력:
      sleeves     : 소매 길이 → clo 계산
      outerwear   : 아우터 착용 → clo 보정
      activity    : 활동 분류 → met 변환

    맥락 신호:
      people      : 재실 인원 수 → 재실 열부하 및 제어 세기
      bags        : 가방 소지 → 퇴근 맥락 점수 (+25)
      heat_source : 조리기구 등 열원 → 복사온도(tr) 보정 및 환기 우선
    """

    # PMV 입력 매핑 테이블 (ISO 7730:2005 근거)
    CLO_BASE  = {'short': 0.5, 'long': 1.0}
    CLO_OUTER = 0.3   # 아우터 착용 시 추가 착의량

    MET_MAP = {
        'lying':      0.8,   # 누워있음 (수면/휴식)
        'sitting':    1.0,   # 착석 (사무 작업)
        'standing':   1.2,   # 기립 (가벼운 활동)
        'walking':    1.5,   # 보행
        'cooking':    2.0,   # 조리 (서서 작업)
        'exercising': 3.0,   # 운동 (유산소)
    }
    MET_DEFAULT = 1.2   # 분류 불가 시 기립 수준
    TR_HEAT_OFFSET = 4.0  # 열원 감지 시 복사온도 보정값 (°C)

    @staticmethod
    def _select_device():
        """
        최적 추론 디바이스 자동 선택
          - Apple Silicon (MPS 사용 가능):  'mps',  float16
          - NVIDIA GPU (CUDA 사용 가능):    'cuda', float16
          - CPU 전용 또는 그 외:            'cpu',  float32
        """
        if torch.backends.mps.is_available():
            return "mps", torch.float16
        if torch.cuda.is_available():
            return "cuda", torch.float16
        return "cpu", torch.float32

    def __init__(self):
        self.device, self.dtype = self._select_device()
        self.model_id = "Qwen/Qwen2-VL-2B-Instruct"

        chip = platform.processor() or platform.machine()
        print(f"🚀 [VLM] {self.device.upper()} ({chip}) 모드로 초기화 중...")

        try:
            if self.device == "mps":
                # Apple Silicon: device_map 미사용, 로드 후 .to('mps')
                self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                    self.model_id,
                    torch_dtype=self.dtype,
                    low_cpu_mem_usage=True,
                ).to(self.device)
            else:
                # CUDA / CPU: device_map으로 직접 배치
                self.model = Qwen2VLForConditionalGeneration.from_pretrained(
                    self.model_id,
                    torch_dtype=self.dtype,
                    low_cpu_mem_usage=True,
                    device_map={"": self.device},
                )
            self.processor = AutoProcessor.from_pretrained(self.model_id)
            print(f"✅ [VLM] {self.model_id} 로드 완료 "
                  f"(device={self.device}, dtype={self.dtype})")
        except Exception as e:
            print(f"❌ [VLM] 모델 로드 실패: {e}")
            self.model     = None
            self.processor = None

    def analyze_frame(self, frame):
        """
        프레임 분석 → PMV 입력 파라미터 + 맥락 신호 반환

        Returns:
            dict: {
                'clo': float,          착의량 (ISO 7730)
                'met': float,          대사율 (ISO 7730)
                'count': int,          재실 인원 수
                'bags': str,           가방 소지 ('yes'|'no')
                'heat_source': str,    열원 존재 ('yes'|'no')
                'outerwear': str,      아우터 착용 ('yes'|'no')
                'activity': str,       활동 분류 원문
            }
            None: 분석 실패 시
        """
        if self.model is None or self.processor is None:
            print("⚠️ [VLM] 모델이 로드되지 않아 분석 불가.")
            return None

        # [최적화] CPU 부하 감소를 위해 160×160으로 다운스케일
        resized = cv2.resize(frame, (160, 160))
        pil_img = Image.fromarray(cv2.cvtColor(resized, cv2.COLOR_BGR2RGB))

        prompt_text = (
            "Analyze this image. Return ONLY a JSON object with these exact keys: "
            "{'sleeves': 'long'|'short', "
            "'outerwear': 'yes'|'no', "
            "'activity': 'lying'|'sitting'|'standing'|'walking'|'cooking'|'exercising', "
            "'people': <integer>, "
            "'bags': 'yes'|'no', "
            "'heat_source': 'yes'|'no'}"
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image", "image": pil_img},
                {"type": "text",  "text": prompt_text},
            ],
        }]

        text            = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        image_inputs, _ = process_vision_info(messages)
        inputs          = self.processor(
            text=[text], images=image_inputs, padding=True, return_tensors="pt"
        )

        # MPS/CUDA: pixel_values를 모델 dtype(float16)으로 캐스팅 후 디바이스 이동
        if self.device in ("mps", "cuda") and "pixel_values" in inputs:
            inputs["pixel_values"] = inputs["pixel_values"].to(self.dtype)
        inputs = inputs.to(self.device)

        with torch.inference_mode():
            generated_ids = self.model.generate(**inputs, max_new_tokens=60, do_sample=False)

        output_text  = self.processor.batch_decode(generated_ids, skip_special_tokens=True)
        raw_response = output_text[0].split('assistant')[-1].strip()

        return self._parse_response(raw_response)

    def _parse_response(self, raw_response: str):
        """VLM 응답 파싱 및 PMV 파라미터 + 맥락 신호 매핑"""
        try:
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                print(f"⚠️ [VLM] JSON 미발견. 응답: {raw_response[:80]}")
                return None

            data = json.loads(json_match.group())

            clo = self.CLO_BASE.get(data.get('sleeves', 'long'), 1.0)
            if data.get('outerwear') == 'yes':
                clo += self.CLO_OUTER

            activity = data.get('activity', 'standing')
            met      = self.MET_MAP.get(activity, self.MET_DEFAULT)

            return {
                "clo":         round(clo, 2),
                "met":         met,
                "count":       max(0, int(data.get('people', 1))),
                "bags":        data.get('bags', 'no'),
                "heat_source": data.get('heat_source', 'no'),
                "outerwear":   data.get('outerwear', 'no'),
                "activity":    activity,
            }

        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as e:
            print(f"⚠️ [VLM] 파싱 실패: {e} | 응답: {raw_response[:80]}")
            return None
