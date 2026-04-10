"""
시나리오 결과 HTML 보고서 생성기
results/ 폴더의 CSV를 읽어 시간대별 표 + 요약을 하나의 HTML로 출력합니다.
"""

from pathlib import Path
import pandas as pd

RESULTS_DIR = Path("results")
OUTPUT_FILE = RESULTS_DIR / "report.html"

# ── 색상 매핑 ──────────────────────────────────────────────────────────────────

def pmv_bg(pmv: float) -> str:
    if abs(pmv) <= 0.5:  return "#d4edda"   # 초록 — 쾌적
    if abs(pmv) <= 1.0:  return "#fff3cd"   # 노랑 — 약간 불쾌
    if abs(pmv) <= 1.5:  return "#ffe5b4"   # 주황 — 불쾌
    return "#f8d7da"                         # 빨강 — 매우 불쾌

def state_badge(state: str) -> str:
    colors = {
        "EMPTY":          ("#6c757d", "공실"),
        "ARRIVAL":        ("#0d6efd", "도착"),
        "STEADY":         ("#198754", "안정"),
        "PRE_DEPARTURE":  ("#fd7e14", "퇴실준비"),
    }
    color, label = colors.get(state, ("#6c757d", state))
    return f'<span style="background:{color};color:#fff;padding:2px 7px;border-radius:4px;font-size:0.8em">{label}</span>'

def hvac_badge(row) -> str:
    if not row["hvac_on"]:
        return '<span style="color:#999">OFF</span>'
    color = "#3399ff" if row["hvac_mode"] == "cool" else "#ff5533"
    label = f"{'냉방' if row['hvac_mode']=='cool' else '난방'} Fan{int(row['fan_speed'])}"
    return f'<span style="color:{color};font-weight:bold">{label}</span>'

def window_badge(w: str) -> str:
    if w == "open":  return '<span style="color:#0dcaf0">🪟 열기</span>'
    if w == "close": return '<span style="color:#6c757d">🔒 닫기</span>'
    return '<span style="color:#aaa">—</span>'

# ── 시나리오 HTML 블록 생성 ────────────────────────────────────────────────────

def scenario_html(csv_path: Path) -> str:
    df = pd.read_csv(csv_path)

    # 1시간(60행) 간격으로 샘플링
    hourly = df.iloc[::60].copy().reset_index(drop=True)

    name = csv_path.stem.replace("_", " ")

    # 요약 통계
    total       = len(df)
    cool_pct    = int((df["hvac_mode"] == "cool").sum() * 100 / total)
    heat_pct    = int((df["hvac_mode"] == "heat").sum() * 100 / total)
    comfort_pct = int((df["pmv"].abs() <= 0.5).sum() * 100 / total)
    pmv_min     = df["pmv"].min()
    pmv_max     = df["pmv"].max()
    t_min       = df["indoor_temp"].min()
    t_max       = df["indoor_temp"].max()

    state_counts = df["state"].value_counts()
    state_dist = " / ".join(
        f"{s}: {state_counts.get(s,0)}분"
        for s in ["EMPTY","ARRIVAL","STEADY","PRE_DEPARTURE"] if state_counts.get(s,0) > 0
    )

    summary = f"""
    <div class="summary">
      <div class="stat"><div class="val">{comfort_pct}%</div><div class="lbl">쾌적 유지율</div></div>
      <div class="stat"><div class="val" style="color:#3399ff">{cool_pct}%</div><div class="lbl">냉방 가동</div></div>
      <div class="stat"><div class="val" style="color:#ff5533">{heat_pct}%</div><div class="lbl">난방 가동</div></div>
      <div class="stat"><div class="val">{pmv_min:+.2f} ~ {pmv_max:+.2f}</div><div class="lbl">PMV 범위</div></div>
      <div class="stat"><div class="val">{t_min:.1f}°C ~ {t_max:.1f}°C</div><div class="lbl">실내 온도 범위</div></div>
    </div>
    <div class="state-dist">상태 분포: {state_dist}</div>
    """

    # 시간대별 표
    rows_html = ""
    for _, row in hourly.iterrows():
        pmv = row["pmv"]
        bg  = pmv_bg(pmv)
        pmv_arrow = "🔥" if pmv > 1.5 else "☀️" if pmv > 0.5 else "❄️" if pmv < -0.5 else "✅"
        rows_html += f"""
        <tr>
          <td><b>{row['time']}</b></td>
          <td>{row['outdoor_temp']:.1f}°C</td>
          <td>{row['indoor_temp']:.1f}°C</td>
          <td style="background:{bg}">{pmv_arrow} {pmv:+.2f}</td>
          <td>{row['comfort']}</td>
          <td>{state_badge(row['state'])}</td>
          <td>{int(row['people'])}명</td>
          <td>{hvac_badge(row)}</td>
          <td>{row['target_temp']:.0f}°C</td>
          <td>{window_badge(row['window_rec'])}</td>
          <td style="font-size:0.8em;color:#555">{str(row['solution'])[:50]}</td>
        </tr>"""

    return f"""
    <div class="scenario-card">
      <h2>{name}</h2>
      {summary}
      <table>
        <thead>
          <tr>
            <th>시각</th>
            <th>실외온도</th>
            <th>실내온도</th>
            <th>PMV</th>
            <th>쾌적도</th>
            <th>상태</th>
            <th>인원</th>
            <th>HVAC</th>
            <th>목표온도</th>
            <th>창문</th>
            <th>솔루션</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
    </div>
    """

# ── 전체 HTML ─────────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Apple SD Gothic Neo', 'Malgun Gothic', sans-serif;
       background: #f0f2f5; color: #222; }
h1 { text-align: center; padding: 28px 0 8px; font-size: 1.8em; color: #1a1a2e; }
.subtitle { text-align: center; color: #666; margin-bottom: 32px; font-size: 0.95em; }
.scenario-card {
  background: #fff; border-radius: 12px; box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  margin: 0 auto 36px; max-width: 1300px; padding: 28px 32px; }
.scenario-card h2 { font-size: 1.25em; color: #1a1a2e; margin-bottom: 16px;
  border-left: 4px solid #4f46e5; padding-left: 12px; }
.summary { display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 10px; }
.stat { background: #f8f9fa; border-radius: 8px; padding: 10px 18px; text-align: center; min-width: 110px; }
.stat .val { font-size: 1.3em; font-weight: bold; color: #1a1a2e; }
.stat .lbl { font-size: 0.75em; color: #888; margin-top: 2px; }
.state-dist { font-size: 0.82em; color: #888; margin-bottom: 16px; }
table { width: 100%; border-collapse: collapse; font-size: 0.88em; }
thead tr { background: #1a1a2e; color: #fff; }
th { padding: 9px 10px; text-align: center; font-weight: 600; white-space: nowrap; }
td { padding: 7px 10px; text-align: center; border-bottom: 1px solid #eee; white-space: nowrap; }
tr:hover td { background: #f5f5ff; }
"""

def build_report():
    csv_files = sorted(RESULTS_DIR.glob("*.csv"))
    if not csv_files:
        print("results/ 폴더에 CSV 파일이 없습니다. 먼저 scenario_runner.py를 실행하세요.")
        return

    cards = "".join(scenario_html(f) for f in csv_files)

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>HVAC 시나리오 분석 보고서</title>
  <style>{CSS}</style>
</head>
<body>
  <h1>🌡️ VLM HVAC 시나리오 분석 보고서</h1>
  <p class="subtitle">시나리오별 24시간 시뮬레이션 결과 — 1시간 단위 요약</p>
  {cards}
</body>
</html>"""

    OUTPUT_FILE.write_text(html, encoding="utf-8")
    print(f"보고서 생성 완료: {OUTPUT_FILE.resolve()}")

if __name__ == "__main__":
    build_report()
