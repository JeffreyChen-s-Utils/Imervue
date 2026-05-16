<p align="center">
  <img src="../Imervue.ico" alt="Imervue Logo" width="128" height="128">
</p>

<h1 align="center">Imervue</h1>

<p align="center">
  <strong>Image + Immerse + View</strong><br>
  PySide6와 OpenGL로 구축된 GPU 가속 이미지 뷰어 / 현상 / 페인트 스튜디오 / 퍼펫 애니메이터
</p>

<p align="center">
  <a href="../README.md">English</a> ·
  <a href="README_zh-TW.md">繁體中文</a> ·
  <a href="README_zh-CN.md">简体中文</a> ·
  <a href="README_ja.md">日本語</a> ·
  <strong>한국어</strong> ·
  <a href="README_es.md">Español</a> ·
  <a href="README_fr.md">Français</a> ·
  <a href="README_de.md">Deutsch</a> ·
  <a href="README_pt-BR.md">Português (BR)</a> ·
  <a href="README_ru.md">Русский</a>
</p>

<p align="center">
  <a href="https://imervue.readthedocs.io/en/latest/?badge=latest"><img src="https://readthedocs.org/projects/imervue/badge/?version=latest" alt="Documentation Status"></a>
  <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
  <img src="https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey" alt="Platform">
</p>

---

## 목차

- [개요](#개요)
- [설치](#설치)
- [사용 방법](#사용-방법)
- [Imervue — 이미지 브라우저 및 라이브러리](#imervue--이미지-브라우저-및-라이브러리)
- [Modify — 비파괴 현상](#modify--비파괴-현상)
- [Paint — 본격 래스터 페인트 스튜디오](#paint--본격-래스터-페인트-스튜디오)
- [Puppet — 2D 리그드 애니메이션](#puppet--2d-리그드-애니메이션)
- [Desktop Pet — 프레임리스 오버레이](#desktop-pet--프레임리스-오버레이)
- [키보드 및 마우스 단축키](#키보드-및-마우스-단축키)
- [메뉴 구조](#메뉴-구조)
- [플러그인 시스템](#플러그인-시스템)
- [MCP 서버](#mcp-서버)
- [다국어 지원](#다국어-지원)
- [사용자 설정](#사용자-설정)
- [아키텍처](#아키텍처)
- [라이선스](#라이선스)

---

## 개요

Imervue는 GPU 가속 이미지 워크스테이션으로 **다섯 개의 최상위 탭**을 제공합니다:

| 탭 | 기능 |
|---|---|
| **Imervue** | 이미지 라이브러리의 탐색, 보기, 정리, 검색, 일괄 처리 |
| **Modify** | 비파괴 현상 파이프라인 — 슬라이더, 커브, LUT, 마스크, 보정, 다중 이미지 합성 |
| **Paint** | 본격 래스터 페인트 스튜디오 — 브러시, 레이어, 애니메이션, 만화 도구, PSD 입출력 |
| **Puppet** | 처음부터 직접 구축한 2D 리그드 퍼펫 애니메이터 — 메시, 디포머, 파라미터, 모션, 물리 |
| **Desktop Pet** | 프레임리스 / 투명 / 항상 위 데스크톱 오버레이로 모든 `.puppet` 리그를 실행 — 라이브 드라이버, 가장자리 스냅, 클릭 통과, 말풍선, 시스템 트레이 |

설계 원칙:

- **성능 우선** — 최신 GLSL 셰이더와 VBO를 활용한 GPU 가속 렌더링
- **대용량 컬렉션 지원** — 가상화된 타일 그리드가 화면에 보이는 썸네일만 로드
- **부드러운 사용 경험** — 비동기 멀티스레드 이미지 로딩과 프리페치
- **비파괴 현상** — 모든 조정은 이미지별 recipe에 저장되며, 명시적으로 내보내기 전까지 원본 파일은 결코 덮어쓰이지 않음
- **확장 가능** — 라이프사이클 / 메뉴 / 이미지 / 입력 훅을 갖춘 완전한 플러그인 시스템; MCP 서버는 Qt 없는 순수 로직 도구를 AI 어시스턴트에 노출

---

## 설치

### 요구 사항

- Python >= 3.10
- OpenGL을 지원하는 GPU (소프트웨어 렌더링 대체도 가능)

### 소스에서 설치

```bash
git clone https://github.com/JeffreyChen-s-Utils/Imervue.git
cd Imervue
pip install -r requirements.txt
```

### 패키지로 설치

```bash
pip install .
```

### 의존성

| 패키지 | 용도 |
|---------|---------|
| PySide6 | Qt6 GUI 프레임워크 |
| qt-material | Material Design 테마 |
| Pillow | 이미지 처리 |
| PyOpenGL | OpenGL 바인딩 |
| PyOpenGL_accelerate | OpenGL 성능 최적화 |
| numpy | 배열 연산 및 썸네일 캐시 |
| rawpy | RAW 이미지 디코딩 |
| imageio | 이미지 입출력 |
| imageio-ffmpeg | 슬라이드쇼 MP4 내보내기 (ffmpeg을 통한 H.264) |
| defusedxml | 안전한 XML 파싱 (XMP 사이드카) |

선택 사항 (기능별 게이트; 설치하지 않으면 해당 기능만 비활성화):

| 패키지 | 용도 |
|---------|---------|
| open_clip_torch + torch | CLIP 시맨틱 검색 (자연어 이미지 쿼리) |
| onnxruntime | Real-ESRGAN AI 업스케일 / CLIP ONNX 자동 태그 |
| opencv-python | HDR 병합, 파노라마 스티칭, 포커스 스태킹, 얼굴 검출, 힐링 브러시 |
| sounddevice | Puppet 마이크 입싱크 |
| mediapipe | Puppet 웹캠 얼굴 추적 |

---

## 사용 방법

### 기본 실행

```bash
python -m Imervue
```

### 특정 이미지나 폴더 열기

```bash
python -m Imervue /path/to/image.jpg
python -m Imervue /path/to/folder
```

### 명령줄 옵션

| 옵션 | 설명 |
|--------|-------------|
| `--debug` | 디버그 모드 활성화 |
| `--software_opengl` | 소프트웨어 OpenGL 렌더링 사용 (`QT_OPENGL=software` 및 `QT_ANGLE_PLATFORM=warp` 설정) |
| `file` | (위치 인자) 시작 시 열 이미지 파일 또는 폴더 |

---

## Imervue — 이미지 브라우저 및 라이브러리

**Imervue** 탭은 기본 진입 화면입니다. 이미지 뷰어를 폴더 트리, EXIF 사이드바, 라이브러리/정리 도구와 결합합니다.

### 뷰어

- **GPU 가속 렌더링** — OpenGL (GLSL 1.20 셰이더 + VBO)
- **딥 줌 피라미드** — 512×512 타일의 다단계 LANCZOS 리샘플링, LRU 캐시 최대 256 타일 / 1.5 GB VRAM 예산, 최대 8× 이방성 필터링
- **비동기 로딩** — 멀티스레드 디코딩 + ±3장 프리페치
- **가상화된 썸네일 그리드** — 화면에 보이는 타일만 렌더링; 썸네일 크기 설정 가능 (128 / 256 / 512 / 1024 / 자동)
- **디스크 캐시** — MD5 기반 무효화를 사용하는 압축 PNG 썸네일, `%LOCALAPPDATA%/Imervue/cache/thumbnails` (또는 `~/.cache/imervue/thumbnails`)에 저장
- **애니메이션 재생** — GIF / APNG, 재생 / 일시정지 / 프레임 단위 / 속도 제어 지원

### 브라우징 모드

- **그리드**(기본) — 가상화된 타일 그리드, 호버 미리보기 팝업(500 ms 지연)
- **목록 (상세)** — `Ctrl+L`로 토글; 열: 미리보기 · 라벨 · 이름 · 해상도 · 크기 · 종류 · 수정 일시
- **딥 줌** — 타일 더블 클릭; GPU로 부드러운 팬/줌 + 미니맵 오버레이
- **분할 뷰** (`Shift+S`) — 두 이미지 나란히 보기
- **양면 페이지 읽기** (`Shift+D`, 우→좌 만화는 `Ctrl+Shift+D`) — 펼침면 리더
- **다중 모니터 미러** (`Ctrl+Shift+M`) — 보조 디스플레이 창
- **시어터 모드** (`Shift+Tab`) — 모든 UI 크롬 숨김
- **비교 다이얼로그** — 나란히 / 오버레이(알파 슬라이더) / 차이(게인 슬라이더) / 드래그 가능한 분할 막대를 사용하는 A|B 분할
- **Timeline / Calendar / Map** 뷰 — 촬영 날짜별 라이브러리 그룹화, 달력 탐색, Leaflet + OpenStreetMap에 지오태그된 사진 표시

### 화면 오버레이

- RGB 히스토그램 (`H`)
- F8 OSD (파일명 / 크기 / 형식), Ctrl+F8 디버그 HUD (VRAM / 캐시 / 스레드)
- 픽셀 뷰 (`Shift+P`) — ≥ 400 % 줌에서 픽셀 격자 + 픽셀별 RGB / HEX 표시
- 색상 모드 (`Shift+M`) — Normal / Grayscale / Invert / Sepia (GLSL)

### 내비게이션

- 방향키, 브라우저식 히스토리 (`Alt+←/→`), 무작위 점프 (`X`)
- 폴더 간 내비게이션 (`Ctrl+Shift+←/→`)
- 인덱스로 이미지 이동 (`Ctrl+G`)
- 퍼지 검색 (`Ctrl+F` / `/`)
- **명령 팔레트** (`Ctrl+Shift+P`) — 모든 메뉴 동작을 퍼지 검색
- 폴더 끝에서 자동 순환
- 트랙패드 핀치 줌 + 가로 스와이프로 이미지 전환

### 정리

- **북마크** — 최대 5000개 경로
- **별점** — 0-5 별 (`1`–`5`) + 즐겨찾기 하트 (`0`)
- **컬러 라벨** — 다른 XMP 인식 사진 관리자와 동일한 플래그 기반 빨강 / 노랑 / 초록 / 파랑 / 보라 (`F1`–`F5`)
- **컬링(Culling)** — 다른 XMP 인식 사진 관리자의 3상태 플래그 (`P` = pick, `Shift+X` = reject, `U` = unflag); 상태별 필터링; 거부된 사진 일괄 삭제
- **계층 태그** — `animal/cat/british` 같은 트리 경로; 하위 항목 자동 매칭
- **Tags & Albums** — 다중 태그 AND / OR 필터링
- **스마트 앨범** — 규칙 기반 쿼리(확장자 / 해상도 / 별점 / 색상 / 컬링 / 태그)를 저장하고 클릭 한 번으로 재적용
- **RAW+JPEG 쌍 스택** — 동일 파일 스템의 캡처를 하나의 타일로 접기; RAW는 형제 항목으로 여전히 접근 가능
- **이미지별 메모** — EXIF 사이드바에서 자동 디바운스 저장, 세션 간 영구 보존
- **스테이징 트레이** — 폴더를 가로지르는 바구니, 재시작 후에도 유지; 일괄 이동 / 복사 / 내보내기
- **듀얼 페인 파일 관리자** — 듀얼 페인 양 트리 뷰
- **세션 / 워크스페이스 레이아웃** — 탭 / 선택 / 필터 / 도크 좌표를 `.imervue-session.json`으로 스냅샷; Browse / Develop / Export 같은 명명된 레이아웃 저장
- **매크로** — 별점 / 즐겨찾기 / 색상 / 태그 동작 배치를 녹화 / 재생 (`Alt+M`은 마지막 매크로 재생)
- **썸네일 배지 + 밀도** — 컬러 스트립 / 즐겨찾기 / 북마크 / 별점 별표; Compact / Standard / Relaxed 패딩
- **외부 앱으로 드래그 아웃** — 타일을 Explorer / Chrome / Discord에 바로 끌어넣기
- **최근 폴더 / 이미지** 추적; 시작 시 마지막 폴더 자동 복원

### 정렬 및 필터

- 이름 / 수정 시각 / 생성 시각 / 크기 / 해상도로 정렬 (오름 / 내림)
- 확장자, 컬러 라벨, 별점, 태그/앨범, 컬링 상태로 필터링
- **고급 필터** — 해상도 / 파일 크기 / 방향 / 수정 일자 범위
- **다중 태그 필터** 다이얼로그 (AND / OR 불리언 로직)

### 검색

- **퍼지 파일명 검색** + 부분 문자열 하이라이트
- **유사 이미지 찾기** — pHash (64-bit DCT), 조정 가능한 Hamming 거리
- **라이브러리 검색** — SQLite 다중 루트 인덱스; 확장자 / 크기 / 해상도 / 파일명으로 쿼리
- **시맨틱 검색 (CLIP)** — 캐시된 임베딩을 통한 자연어 쿼리 ("눈 속의 골든 리트리버"); `open_clip_torch` + `torch`가 설치되지 않으면 우아하게 비활성화
- **자동 태그** — 휴리스틱 분류 + 선택적 CLIP ONNX 업그레이드

### 메타데이터

- **EXIF 사이드바** — 접을 수 있는 그룹 + 인라인 0-5 별점 스트립
- **EXIF 편집기** 다이얼로그
- **이미지 정보** 다이얼로그 (크기 / 용량 / 날짜)
- **XMP 사이드카** (`.xmp` 동반 파일) — 별점 / 제목 / 설명 / 키워드 / 컬러 라벨을 다른 XMP 인식 사진 관리자와 양방향 동기화 (`defusedxml`을 통한 안전한 XML 파싱)
- **GPS 지오태그 편집기** — EXIF GPS 위도/경도 읽기/쓰기 (JPEG)
- **토큰 일괄 이름 변경** — 라이브 미리보기 템플릿 `{date:yyyymmdd}_{camera}_{counter:04}{ext}`
- **메타데이터 CSV / JSON 내보내기** — 컬링 / 별점 / 태그 / 메모를 포함한 이미지당 한 행

### 추가 도구 (Imervue 탭 — 일괄 처리)

**Tools** 메뉴에서 접근; 기능별로 묶인 서브메뉴로 정리:

- **Batch** — 포맷 변환 · EXIF 제거 · 이미지 새니타이저(숨겨진 데이터를 제거하기 위해 다시 렌더링) · 이미지 정리기(날짜 / 해상도 / 종류 / 크기별로 하위 폴더에 정렬) · 토큰 일괄 이름 변경
- **AI / 휴리스틱** — AI 이미지 업스케일 (Real-ESRGAN x2 / x4 + ONNX Runtime CUDA/DML/CPU) · 중복 이미지 찾기 · 유사 이미지 찾기 · 자동 태그 · 얼굴 검출 (Haar cascade)
- **라이브러리 및 메타데이터** — 라이브러리 검색 · 스마트 앨범 · 계층 태그 · 메타데이터 내보내기 · XMP 사이드카 · GPS 지오태그

### 시스템 통합

- Windows 우클릭 **Open with Imervue** 컨텍스트 메뉴 (레지스트리 기반 파일 연결)
- `QFileSystemWatcher`를 이용한 폴더 모니터링 (변경 시 자동 새로고침)
- 토스트 알림 시스템 (info / success / warning / error)
- 온라인 플러그인 다운로더가 포함된 플러그인 시스템 ([플러그인 시스템](#플러그인-시스템) 참조)

---

## Modify — 비파괴 현상

**Modify** 탭은 현상 작업장입니다. 모든 조정은 파일과 함께 보관되는 이미지별 **recipe**에 저장되며, **Export** 또는 **Save As**를 명시적으로 실행하기 전까지 디스크상의 원본 픽셀은 결코 덮어쓰이지 않습니다.

### 현상 슬라이더

- 화이트 밸런스 — 색온도 / 틴트
- 톤 영역 — 그림자 / 미드톤 / 하이라이트
- 노출 / 대비 / 채도 / 활기
- 자르기, 회전, 좌우 / 상하 반전
- 모든 편집은 비파괴로 유지되며 recipe 저장소를 통해 양방향 보존

### 커브 및 LUT

- **톤 커브 편집기** — 드래그 가능한 RGB 커브와 채널별 R / G / B 커브 (monotone cubic 보간)
- **.cube LUT 적용** — 임의의 Adobe 3D LUT 로드 (최대 64³), trilinear 보간, 강도 슬라이더로 블렌드
- **스플릿 토닝** — 플래그 기반 그림자 / 하이라이트 색조 + 채도, 균형 피벗 포함

### 로컬 조정

- **브러시 / 방사형 / 선형 그라데이션 마스크** — 마스크별 노출 / 밝기 / 대비 / 채도 / 화이트 밸런스 델타 + 페더 슬라이더
- 마스크는 현상 파이프라인을 통해 비파괴로 블렌드

### 보정 및 변형

- **힐링 브러시** — 원형 스팟, OpenCV inpainting (Telea 또는 Navier-Stokes)
- **클론 스탬프** — Shift+클릭으로 소스 지정, 페더 블릿으로 대상에 복제
- **자르기 / 수평 보정** — 정규화된 자르기 사각형과 임의 각도 수평 보정, 최대 내접 직사각형으로 자동 자르기
- **자동 수평 보정** — Hough 라인 기반 수평선 / 수직선 검출
- **렌즈 보정** — 순수 numpy 방사형 왜곡 (배럴 / 핀쿠션), 비네팅 보정, 채널별 색수차 보정
- **노이즈 감소 / 샤프닝** — 엣지 보존 양방향 노이즈 제거 + unsharp mask 샤프닝
- **하늘 / 배경** — 검출된 하늘을 그라데이션으로 교체하거나 배경 제거 (투명 또는 흰색 채우기); 선택적 `rembg` / U²-Net 업그레이드

### 다중 이미지

- **HDR 병합** — OpenCV Mertens fusion을 통해 브라케팅 노출 결합 (AlignMTB 사전 정렬 포함)
- **파노라마 스티칭** — OpenCV `Stitcher` (panorama 또는 scans 모드), 검정 테두리 자동 자르기
- **포커스 스태킹** — Laplacian-variance 포커스 맵 + Gaussian 블렌드, 선택적 ECC 정렬

### 출력

- **워터마크 오버레이** — 텍스트 또는 이미지, 9개 앵커 위치, 불투명도, 스케일; 내보내기 시에만 적용
- **내보내기 프리셋** — Web 1600 / Print 300 dpi / Instagram 1080 원클릭 파이프라인
- **Save As / Export** — PNG / JPEG / WebP / BMP / TIFF, 손실 포맷에는 품질 슬라이더
- **일괄 작업** — 이름 변경, 이동/복사, 선택한 이미지 회전
- **컨택트 시트 PDF** — 캡션이 있는 다중 페이지 그리드 (A4 / A3 / Letter / Legal)
- **웹 갤러리 HTML** — `index.html` + JPEG 썸네일 + 인라인 라이트박스가 포함된 자체 완결 폴더
- **슬라이드쇼 MP4** — H.264 비디오, 설정 가능한 FPS / 이미지당 유지 시간 / 페이드 전환 (`imageio-ffmpeg`)
- **인쇄 레이아웃** — 설정 가능한 페이지 크기 / 방향 / 그리드 / 여백 / 거터 / 재단선이 있는 다중 페이지 PDF 시트
- **소프트 프루프** — ICC 프로파일 로드, 대상 색역 시뮬레이션, 색역 밖 픽셀을 마젠타로 강조
- **가상 사본** — 이미지별 명명된 recipe 스냅샷; 마스터를 잃지 않고 여러 룩 사이를 전환

### 외부 편집기

**File > External Editors…**에 프로그램(your image editor 등)을 등록하고, **File > Open in External Editor**로 현재 이미지를 해당 편집기에서 열 수 있습니다.

---

## Paint — 본격 래스터 페인트 스튜디오

**Paint** 탭은 자체 `QMainWindow`에 임베드된 본격 래스터 페인트 스튜디오로, 메뉴, 왼쪽 도구 스트립, 컨텍스트 감지 옵션 바, 오른쪽 탭형 도크 컬럼을 갖춥니다. 멀티탭 도큐먼트 편집 — 여러 그림을 동시에 열고 각각 독립적인 실행 취소 스택을 보유합니다.

### 도구 (24개)

브러시 · 지우개 · 채우기 · 스포이드 · 사각형 / 올가미 / 마법봉 / 빠른 선택 · 이동 · 텍스트 · 그라데이션 · 블러 · 스머지 · 펜 · 클론 스탬프 · 말풍선 · 사각형 · 타원 · 직선 · 다각형 · 자르기 · 변형 · 핸드 · 줌

단일 키 단축키: `B / E / G / I / V / T / U / R / P / S / C / Z / H`; 도형 변형은 `Shift+R/E/I/P`.

### 브러시

펜 / 마커 / 연필 / 형광펜 / 스프레이 / 캘리그래피 / 수채화 / 목탄 / 크레용, Size / Opacity / Hardness / Density / 블렌드 모드 제어 포함. 압력 커브 편집기, 선택 영역으로부터 브러시 팁 캡처, 브러시 프리셋 가져오기 / 내보내기.

### 레이어

썸네일, 가시성 토글, 드래그로 순서 변경, 블렌드 모드, 불투명도, 검색, 벡터 레이어, 1-bit 레이어, **레이어 마스크**(추가 / 선택에서 / 반전 / 적용), **클리핑 마스크**, **레이어 효과**(드롭 섀도 / 외부 광선 / 스트로크)를 갖춘 완전한 레이어 패널. 색상으로 레이어 분할, 그라데이션 맵 프리셋.

### 선택

사각형 / 올가미 / 마법봉 / 빠른 선택, **교체 / 추가 / 빼기 / 교차** 모드 + 페더. **퀵 마스크 모드** (`Q`) — 마스크를 그려서 작업하는 워크플로우용. **선택 영역 획**(Stroke Selection) 다이얼로그.

### 애니메이션 및 만화

- **애니메이션** — 스냅샷, 재생, 어니언 스킨 오버레이, MP4 / GIF 내보내기를 갖춘 프레임 타임라인 도크
- **만화 도구** — 패널 컷터 · 톤 레이어 · 페이지 번호 스탬프 · 스피드라인(방사 / 평행 / 버스트) · 액션 플래시 · 말풍선 도구

### 필터 및 보기 보조

- **필터** — Levels · Curves · Posterize · Threshold · Auto Color Balance · Film Grain · Halftone (각각 라이브 미리보기 다이얼로그 포함)
- **보기 보조** — 픽셀 격자 · 픽셀에 스냅 · 가장자리에 스냅 · 어니언 스킨 · 블리드 가이드 · 캔버스 회전 (`Ctrl+Shift+H`로 반시계 방향 회전)

### 도크 (10개, 탭형)

Color · Brush · Layer · Navigator · 머티리얼 라이브러리 · History · Swatch · Reference · Histogram · Animation. 각 도크는 이동 / 플로팅 가능. **Settings > Workspace Layouts**로 명명된 배치를 저장 및 호출.

### 파일 입출력

- **PSD** (Photoshop) 열기 / 저장, 레이어 양방향 보존
- PNG / JPEG / WebP 내보내기, 그리고 다중 페이지 만화를 **CBZ** 또는 **PDF**로 내보내기
- 자동 저장 스냅샷 + 최신 복원

### 파워 유저 UX

- **Tab**으로 모든 도크 토글 (무방해 페인팅)
- `Ctrl+Tab`으로 탭 순환
- `,` / `.`로 브러시 종류 순환
- `0`-`9`로 브러시 불투명도 10 % 단위 설정
- `Alt+[` / `Alt+]`로 활성 레이어 단계 이동
- 캔버스 우클릭으로 빠른 Undo / Redo / 전체 선택 / 선택 해제 / Fit / 100 % 메뉴 열기
- 탭별 수정됨 별표, undo / redo 토스트 확인, 시작 시 자동 저장 복구 프롬프트

딥 줌에서 `E`를 누르면 현재 이미지가 새로운 Paint 탭으로 바로 보내집니다.

---

## Puppet — 2D 리그드 애니메이션

**Puppet** 탭은 처음부터 직접 구축한 2D 리그드 퍼펫 애니메이션 시스템입니다. Live2D가 하는 일(메시 변형 리그, 파라미터, 모션, 물리, 표정, 포즈, 입싱크, 웹캠 얼굴 추적)을 수행하지만 **독점 SDK 없이**, **`live2d-py` 없이**, 그리고 `Imervue/puppet/FORMAT.md`에 완전히 문서화된 완전 개방형 `.puppet` 파일 형식을 사용합니다.

> **전체 가이드**: [`puppet_guide.md`](../puppet_guide.md)는 라이브 스트리밍(OBS / NDI / 가상 카메라)과 애니메이션 제작(녹화 / 타임라인 편집 / MP4 내보내기) 양쪽의 엔드 투 엔드 워크플로우를 다룹니다. 중국어판은 [`puppet_guide.zh-TW.md`](../puppet_guide.zh-TW.md) 및 [`puppet_guide.zh-CN.md`](../puppet_guide.zh-CN.md)에 있습니다.

### 파일 형식

`.puppet`은 zip 컨테이너입니다:

- `puppet.json` — manifest (drawables, deformers, parameters, motions, pose groups, parts, hit areas)
- `textures/*.png` — 아틀라스 텍스처
- `motions/*.json` — keyframe 트랙
- `expressions/*.json` — 파라미터 오버레이
- `physics.json` — Verlet 리그 구성

JSON 기반, 사람이 diff 가능, 독점 바이너리 없음.

### 렌더러

`QOpenGLWidget`로 draw_order에 따른 vertex-array 텍스처 트라이앵글 드로잉, drawable별 블렌드 모드(normal / additive / multiply), pose-group 배타성, 이미지 공간 직교 투영, GL_REPEAT 타일링된 투명도 체커 배경, 휠 줌 + 중간 버튼 드래그 팬을 제공합니다. 대형 리그에 최적화 — March 7th (drawable 307개 / vertex morph 2965개)가 CPU에서 60 FPS로 동작.

### 작성

- **PNG 가져오기** → 알파를 고려한 삼각 그리드 메시 자동 생성
- **회전 디포머 추가** (anchor + angle) / **워프 디포머 추가** (rows × cols 베지에 격자) 툴바 액션
- **파라미터 추가** → 파라미터 도크의 **Set Key**로 슬라이더 양 끝에서 key 형태 설정
- **메시 편집기** — Edit Mesh를 토글하여 정점 드래그; 8 px 이내 클릭은 가장 가까운 정점에 스냅
- **Save As…** — 전체 리그를 `.puppet` zip으로 저장

### 런타임

- **파라미터 리그** — 각 파라미터는 슬라이더 값을 부분 디포머 형태 스냅샷에 매핑하는 key 리스트를 보유; 런타임에서 샘플링하여 필드별 lerp
- **모션 재생** — 모션 목록 + Play / Pause / Stop / Loop / 스크럽이 있는 하단 도크; 커브 샘플러는 `linear`, `stepped`, `inverse-stepped`, `cubic-bezier` 세그먼트를 지원(Newton 반복으로 time → param 해결); 모션별 페이드 인 / 페이드 아웃
- **표정** — `additive` / `multiply` / `overwrite` 파라미터 오버레이 스택
- **포즈 그룹** — 상호 배타적인 drawable 가시성 (무기 교체, 입 모양 변형)
- **물리** — 머리카락 / 옷 / 리본을 위한 Verlet 진자 체인; 입력 파라미터가 체인 앵커를 이동시키고, 중력 + 감쇠 + 입자별 스프링이 정지 상태로 복귀
- **정점 모프** — Cubism 스타일 rest와 ±extreme 델타 사이의 선형 블렌드; numpy 벡터화로 60 FPS 매 프레임
- **불투명도 keys** — 파라미터 구동 알파 커브; 제스처 파라미터에 따라 대체 포즈 메시가 페이드 인/아웃

### 라이브 입력

- 커서 드래그 → 머리 각도 파라미터
- 코사인 open → close → open 커브 기반 자동 눈깜빡임
- `sounddevice` RMS를 통한 마이크 입싱크 → `ParamMouthOpenY` (선택 의존성)
- OpenCV + MediaPipe FaceMesh를 통한 웹캠 얼굴 추적 → 머리 yaw / pitch / roll + 눈 / 입 개폐 (선택 의존성)
- 커스텀 모션 녹화 — 슬라이더를 흔들고 / 웹캠을 향하고 / 물리가 동작하는 동안 30 Hz로 파라미터 값을 캡처; 정지 시 재생 / 루프 / 저장 준비된 선형 세그먼트 Motion으로 베이킹

### Cubism 상호운용

**Cubism Native SDK**를 플러그인할 수 있어(사용자 제공 DLL — Live2D의 Free Material License는 재배포를 금지) 어떤 `.moc3` 모델이든 `.puppet` zip으로 변환할 수 있습니다. 컨버터는 정점 모프 델타와 파라미터 구동 가시성 전환을 모두 캡처하는 sample-and-reconstruct 스윕을 실행하므로, 제스처 전환(브이 사인 / 얼굴 가리기 / 사진 …)이 변환 후에도 그대로 유지됩니다.

### 출력

- **Capture frame…** — `glReadPixels`로 현재 캔버스를 PNG로 저장
- **Record…** — 30 FPS 프레임 루프를 토글하여 `imageio`를 통해 GIF / WebM / MP4로 저장
- **가상 카메라** — 퍼펫 캔버스를 시스템 웹캠으로 노출
- **NDI 출력** — LAN에서 퍼펫을 NDI 소스로 브로드캐스트
- **VTube Studio API 서버** — VTS 호환 클라이언트를 위한 선택적 WebSocket API

### OBS 라이브 스트리밍

두 가지 지원 경로가 있습니다. "그냥 동작"을 원하면 A를, 빠른 LAN에서 가장 낮은 지연과 최고 품질을 원하면 B를 고르세요.

#### A. 가상 카메라 (가장 쉬움)

퍼펫 캔버스가 웹캠으로 나타나고 OBS는 표준 Video Capture Device 소스로 이를 가져옵니다.

1. `pip install pyvirtualcam`
2. 플랫폼 드라이버 설치:
   - **Windows**: OBS Studio 26+에 *OBS Virtual Camera* 드라이버가 포함되어 있습니다. OBS 설치 후 한 번 실행하여 우측 하단 패널에서 **Start Virtual Camera**를 클릭하면 드라이버가 시스템 전역에 등록되어 `pyvirtualcam`이 찾을 수 있습니다.
   - **macOS**: OBS for Mac은 OBS Virtual Camera 시스템 확장을 포함합니다. 처음 실행 시 시스템 설정 → 개인 정보 보호 및 보안에서 활성화하라는 프롬프트가 표시됩니다.
   - **Linux**: `sudo modprobe v4l2loopback exclusive_caps=1 card_label="Imervue"` (먼저 `v4l2loopback-dkms` 설치).
3. Puppet 탭에서 리그를 열고 **Output > Virtual camera**를 토글합니다. 상태 표시줄에 선택할 정확한 장치명이 표시됩니다.
4. OBS에서: **Sources > + > Video Capture Device**, 3단계에서 표시된 장치명(보통 *OBS Virtual Camera*)을 선택합니다.

Imervue는 스트리밍 출력의 긴 변을 1080 px로 캡하므로 Cubism 네이티브 캔버스(March 7th은 3503×7777)가 DirectShow 가상 카메라 드라이버에 거부되지 않습니다. 종횡비는 유지되며, 필요하면 OBS에서 더 스케일할 수 있습니다.

##### 왜 배경이 마젠타인가? (그리고 제거하는 방법)

가상 카메라는 **DirectShow**(Windows) / **AVFoundation**(macOS) / **v4l2loopback**(Linux) 위에서 동작합니다. 이 세 전송 방식은 모두 **RGB 전용 — 알파 채널 없음**입니다. OBS의 *Video Capture Device* 소스는 카메라가 보내는 무엇이든 불투명 RGB로 취급하므로, Imervue가 캐릭터 뒤에 어떤 색을 두든 OBS는 그 색을 표시합니다.

Imervue는 그 배경으로 **마젠타 `#FF00FF`**를 선택합니다. 업계 표준 크로마키 색이기 때문입니다: 피부, 머리카락, 눈동자 색에는 거의 나타나지 않으므로 크로마키 임계값을 캐릭터를 침범하지 않고 넓게 열 수 있습니다.

OBS에서 마젠타를 제거하려면:

1. 추가한 *Video Capture Device* 소스 우클릭 → **필터(Filters)**
2. 좌측 하단 **효과 필터(Effect Filters)** 패널 → **+** → **컬러 키(Color Key)**
3. 설정:
   - **Key Color Type**: `Custom Color`
   - **Custom Color**: HEX `FF00FF` (또는 R = 255 / G = 0 / B = 255)
   - **Similarity**: `80`부터 시작, 마젠타 가장자리가 남으면 `200–300`까지 올립니다. 높을수록 더 적극적으로 제거.
   - **Smoothness**: `30–50`으로 가장자리를 부드럽게 하여 컷이 단단해 보이거나 픽셀화되지 않도록.
4. 다이얼로그를 닫습니다. OBS는 필터를 소스에 첨부하므로, 다음에 가상 카메라를 활성화할 때 크로마 키가 자동으로 적용됩니다.

캐릭터의 팔레트에 마젠타가 있다면(드물지만 의상 / 소품에서 가능), 크로마 키가 그 픽셀도 잡아먹습니다. 아래의 NDI 경로로 전환하세요 — NDI는 알파 채널을 직접 전달하므로 크로마 키가 필요 없습니다.

**문제 해결: OBS에 여전히 마젠타가 보임**

- Color Key 필터가 **Video Capture Device** 소스에 첨부되어 있는지 확인하세요, Scene이 아니라. 소스의 필터는 소스와 함께 이동하지만, Scene의 필터는 소스가 렌더링된 후에 위에 적용됩니다.
- HEX가 정확히 `FF00FF`인지 확인 — `FF00FE` 등은 모든 마젠타 픽셀을 잡지 못합니다.
- 캐릭터 외곽선에 마젠타 픽셀의 얇은 후광이 있다면 *Similarity*를 `300`까지 올리세요. 가장자리는 마젠타 배경에 대한 GL_LINEAR 보간에서 오므로, 더 넓은 similarity 허용치가 이를 잡아먹습니다.

#### B. NDI (가장 낮은 지연, 프로급)

NDI(Newtek의 Network Device Interface)는 알파 채널이 그대로 유지된 채 LAN을 통해 50 ms 미만의 지연으로 퍼펫을 전달합니다.

1. <https://ndi.video/tools/>에서 **NDI Tools**를 다운로드 및 설치(NDI 런타임 포함).
2. `pip install ndi-python`
3. **obs-ndi** 플러그인을 OBS에 설치: <https://github.com/obs-ndi/obs-ndi/releases>
4. Puppet 탭에서 **Output > NDI output**을 토글합니다. 상태 표시줄이 NDI 소스명(기본 *Imervue Puppet*)을 보고합니다.
5. OBS에서: **Sources > + > NDI Source**, 4단계의 소스를 선택합니다.

NDI는 경로 A와 동일한 1080 캡 해상도로 브로드캐스트하지만 RGBA를 전달합니다 — 오프스크린 렌더가 캐릭터 외부에 투명 배경을 생성하고, NDI는 알파 채널을 그대로 전송하며, OBS / vMix는 어떤 크로마 키 패스도 없이 퍼펫을 바로 씬 위에 합성합니다.

#### C. 윈도우 캡처 (최후의 수단)

OBS **Sources > + > Window Capture**는 Imervue 창을 직접 잡을 수 있으며 별도 의존성이 필요 없습니다. 화질은 떨어지고 UI 크롬을 직접 잘라내야 하지만, 드라이버를 설치할 수 없는 제한된 환경에서도 동작합니다.

### 데모

손쉽게 사용 가능한 리그는 [`examples/puppet/march_7th.puppet`](../examples/puppet/march_7th.puppet)에 있습니다 — 트리 내에서 변환된 307 drawable Cubism Live2D 캐릭터. **Open Puppet…**으로 열면 리그가 중앙에 로드됩니다; 18개 모션(Idle 그룹 + Gesture 그룹) 중 아무거나 클릭하여 재생하세요. 제스처는 브이 사인, 얼굴 가리기, 사진, 홍조, 어두운 얼굴, 울음, 땀, 별, 별똥별을 포함합니다 — 리그가 정의하는 모든 명명된 제스처.

---

## Desktop Pet — 프레임리스 오버레이

탭 5 — **Desktop Pet**은 모든 `.puppet` 캐릭터를 데스크톱 위에 프레임리스 / 투명 오버레이로 띄웁니다. 탭 자체는 컨트롤 패널이며, 실제 캐릭터는 다른 창들 위(또는 뒤)에 떠 있습니다. Puppet 탭에서 리그로 할 수 있는 모든 것 — 모션, 표정, 물리, 아이들 드라이버, 웹캠 / 마이크 입력 — 이 여기에서도 똑같이 동작합니다.

### 할 수 있는 것들

| 기능 | 설명 |
|---|---|
| 프레임리스 오버레이 | 창 크롬도 작업 표시줄 항목도 없이 — 캐릭터만 데스크톱에 떠 있습니다. |
| 투명 배경 | 캐릭터가 덮지 않는 모든 곳은 데스크톱이 그대로 비칩니다. |
| 드래그로 이동 | 캐릭터를 왼쪽 드래그하여 원하는 위치로 옮깁니다. 화면 가장자리 근처에서 놓으면 가장자리에 딱 맞게 **스냅**됩니다. |
| 클릭 통과 모드 | 펫이 마우스를 무시하도록 만들어 펫 아래에서 작업을 계속할 수 있습니다. |
| 위치 잠금 | 펫을 고정하여 우발적인 드래그가 위치를 움직이지 못하게 합니다. |
| 항상 맨 아래 | 펫을 다른 모든 창 뒤에 배치 — 항상 위가 아닌 데스크톱 위젯 같은 느낌. |
| 전체 화면 시 숨김 | 같은 모니터에서 다른 앱(게임 / 동영상 / 프레젠테이션)이 전체 화면일 때 자동으로 숨기고, 전체 화면이 끝나면 다시 나타납니다. |
| 숨겨졌을 때 일시 정지 | 보이지 않는 동안에는 펫이 애니메이션을 멈춰 화면 밖일 때는 CPU 사용량이 0입니다. |
| 크기 프리셋 | 소형 / 중형 / 대형. 중앙 기준으로 크기가 바뀌므로 펫이 화면을 가로질러 튀지 않습니다. |
| 불투명도 슬라이더 | 펫을 10%에서 100%까지 페이드하여 은은한 데스크톱 장식으로 만들 수 있습니다. |
| 위치 기억 | 펫을 좋아하는 모퉁이로 드래그해 두면 다음 실행 시 그 자리로 돌아옵니다. |

### 클릭 상호작용

- **본체에서 왼쪽 클릭** — 리그에 hit area가 정의되어 있으면(예: 머리 탭) 매칭되는 모션이 재생됩니다. 그렇지 않으면 펫이 말풍선으로 인사합니다.
- **어디서나 오른쪽 클릭** — 컨텍스트 메뉴를 엽니다: 펫 숨기기, Live drivers, Play motion(리그의 모든 모션 목록), Apply expression, 위치 잠금, 클릭 통과, 항상 맨 아래, 전체 화면 시 숨김, 말풍선, 크기.
- **시스템 트레이 아이콘** — 왼쪽 클릭으로 가시성을 토글하고, 오른쪽 클릭으로 Show/Hide, Click-through, Open puppet, Hide pet 메뉴를 엽니다.

### 라이브 드라이버

탭이나 오른쪽 클릭 메뉴에서 원하는 조합을 골라 켜세요. 각 항목은 기본적으로 꺼져 있으며, 원하는 것만 켜면 됩니다.

- **Auto idle** — 캐릭터가 살아 있는 느낌이 들도록 호흡 + 미세한 드리프트를 더합니다.
- **Idle motions** — 리그의 아이들 그룹 모션을 무작위로 순환 재생합니다.
- **Auto-blink** — 몇 초마다 자연스러운 눈 깜박임 사이클.
- **Drag-track head** — 머리가 커서를 따라 돌아갑니다.
- **Mic lip-sync** — 음성에 맞춰 입이 열립니다 (`sounddevice` 필요).
- **Webcam tracking** — 사용자의 머리 / 눈 / 입이 퍼펫을 움직입니다 (`opencv-python`과 `mediapipe` 필요).

### 시작하는 방법

1. **Desktop Pet** 탭으로 전환합니다.
2. **Load bundled March 7th**를 클릭하여 번들된 캐릭터를 쓰거나, **Open Puppet…**으로 직접 `.puppet` 파일을 고릅니다.
3. **Show pet on desktop**을 체크합니다.
4. 캐릭터를 원하는 위치로 드래그하고, 원하는 드라이버를 고르고, 불투명도 / 크기를 조정합니다.
5. 언제든 오른쪽 클릭으로 빠른 동작 메뉴를 열거나, 탭을 찾지 않고도 시스템 트레이 아이콘으로 펫을 숨길 수 있습니다.

설정한 모든 항목 — 위치, 드라이버, 불투명도, 클릭 통과, 크기 — 은 실행 사이에 기억됩니다.

---

## 키보드 및 마우스 단축키

### 내비게이션 (모든 모드)

| 단축키 | 동작 |
|----------|--------|
| 방향키 | 그리드 스크롤 / 이미지 전환 (딥 줌에서는 좌/우) |
| Shift + 방향 | 세밀 스크롤 (반 단계) |
| Ctrl+Shift+←/→ | 이미지가 있는 이전 / 다음 형제 폴더로 점프 |
| Alt+← / Alt+→ | 히스토리 뒤로 / 앞으로 |
| Ctrl+G | 인덱스로 이미지 이동 |
| X | 무작위 이미지로 점프 |
| Home | 줌과 팬을 원점으로 리셋 |
| Ctrl+F 또는 / | 퍼지 검색 다이얼로그 열기 |
| Ctrl+Shift+P | 명령 팔레트 열기 |
| Alt+M | 현재 선택에서 마지막 매크로 재생 |
| S | 슬라이드쇼 다이얼로그 열기 |
| Ctrl+Z | 실행 취소 |
| Ctrl+Shift+Z / Ctrl+Y | 다시 실행 |

### 딥 줌 / 단일 이미지

| 단축키 | 동작 |
|----------|--------|
| F | 전체 화면 토글 |
| Shift+Tab | 시어터 모드 토글 (모든 UI 크롬 숨김) |
| R / Shift+R | 시계 / 반시계 방향 회전 |
| E | 이미지 편집기 열기 (Modify 탭) |
| W / Shift+W | 너비 / 높이에 맞춤 |
| H | RGB 히스토그램 오버레이 토글 |
| F8 / Ctrl+F8 | OSD 오버레이 / 디버그 HUD |
| Shift+P | 픽셀 뷰 토글 (≥ 400 % 줌에서 격자 + RGB 표시) |
| Shift+M | 색상 모드 순환 (Normal / Grayscale / Invert / Sepia) |
| B | 북마크 토글 |
| Ctrl+C / Ctrl+V | 클립보드에서 / 로 이미지 복사 / 붙여넣기 |
| 0 / 1-5 | 즐겨찾기 / 빠른 별점 토글 |
| F1-F5 | 빠른 컬러 라벨 (빨강 / 노랑 / 초록 / 파랑 / 보라) |
| P / Shift+X / U | 컬링: Pick / Reject / Unflag |
| Shift+S | 분할 뷰 |
| Shift+D / Ctrl+Shift+D | 양면 페이지 (LTR / RTL) |
| Ctrl+Shift+M | 다중 모니터 미러 창 |
| Delete | 휴지통으로 이동 (실행 취소 가능) |
| Escape | 딥 줌 종료 / 전체 화면 종료 |

### 애니메이션 재생 (GIF / APNG)

| 단축키 | 동작 |
|----------|--------|
| Space | 재생 / 일시정지 |
| , (콤마) / . (마침표) | 이전 / 다음 프레임 |
| [ / ] | 재생 속도 감소 / 증가 |

### 타일 그리드

| 단축키 | 동작 |
|----------|--------|
| Ctrl+L | 그리드 ↔ 목록 토글 |
| 호버 (500 ms) | 호버 미리보기 팝업 |
| Delete | 선택한 타일 삭제 |
| Escape | 전체 선택 해제 |

### 마우스 / 트랙패드

| 동작 | 동작 |
|--------|----------|
| 왼쪽 클릭 | 타일 선택 또는 이미지 열기 |
| 왼쪽 드래그 | 그리드에서 사각형 다중 선택 |
| 길게 누르기 (500 ms) | 타일 선택 모드 진입 |
| 중간 드래그 | 딥 줌에서 팬 |
| 스크롤 휠 | 줌 인/아웃 또는 스크롤 |
| 오른쪽 클릭 | 컨텍스트 메뉴 |
| 핀치 | 딥 줌에서 줌 인/아웃 |
| 가로 스와이프 | 이전 / 다음 이미지 |

### Paint 탭 (위에 추가로)

| 단축키 | 동작 |
|----------|--------|
| B / E / G / I | 브러시 / 지우개 / 채우기 / 스포이드 |
| V / T / U / R | 이동 / 텍스트 / 그라데이션 / 사각형 선택 |
| P / S / C / Z / H | 펜 / 스머지 / 클론 / 줌 / 핸드 |
| Q | 퀵 마스크 모드 토글 |
| Tab | 모든 도크 토글 |
| Ctrl+Tab | Paint 탭 순환 |
| , / . | 브러시 종류 순환 |
| 0-9 | 브러시 불투명도 10% 단계 |
| Alt+[ / Alt+] | 활성 레이어 아래 / 위로 이동 |

---

## 메뉴 구조

### File

- New Window
- Open Image / Open Folder
- Recent (폴더 + 이미지)
- Bookmarks / Tags & Albums
- Commit Pending Deletions
- Paste from Clipboard / Auto-annotate Clipboard Images
- File Association (Windows)
- **Session** — Save / Load
- **Workspaces…** — 명명된 창 레이아웃 저장 / 로드 / 이름 변경
- **External Editors…** + **Open in External Editor**
- Keyboard Shortcuts (커스터마이즈 가능한 바인딩)
- Exit

### Tools (추가 도구 — 8개의 그룹화된 서브메뉴로 정리)

- **Batch** — 포맷 변환 · EXIF 제거 · 이미지 새니타이저 · 이미지 정리기 · 토큰 일괄 이름 변경
- **Library & Metadata** — 라이브러리 검색 · 스마트 앨범 · 유사 / 중복 찾기 · 자동 태그 · 계층 태그 · 메타데이터 내보내기 · XMP 사이드카 · GPS 지오태그
- **Views** — Timeline · Calendar · Map
- **Workflow** — Culling · 스테이징 트레이 · 가상 사본 · 듀얼 페인 파일 관리자 · 매크로
- **Export** — 컨택트 시트 PDF · 웹 갤러리 · 슬라이드쇼 비디오 (MP4) · 인쇄 레이아웃
- **Develop (Non-Destructive)** — 톤 커브 · .cube LUT · 스플릿 토닝 · 로컬 조정 마스크 · 소프트 프루프
- **Retouch & Transform** — AI 이미지 업스케일 · 노이즈 감소 / 샤프닝 · 힐링 브러시 · 클론 스탬프 · 얼굴 검출 · 하늘 / 배경 · 자르기 / 수평 보정 · 자동 수평 보정 · 렌즈 보정
- **Multi-Image** — HDR 병합 · 파노라마 스티칭 · 포커스 스태킹

### View / Sort / Filter / Language / Plugins / Instructions

(표준 메뉴 — 전체 옵션은 앱 내에서 확인.)

### 우클릭 컨텍스트 메뉴

내비게이션 · 빠른 동작(드러내기 / 경로 복사 / 이미지 복사) · 변형 · 일괄 작업 · 삭제 · 배경화면 · 비교 / 슬라이드쇼 · 내보내기 · 추가 도구 · 북마크 · 이미지 정보 · 플러그인 기여 항목.

---

## 플러그인 시스템

Imervue는 서드파티 플러그인을 지원합니다. 전체 참조는 [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md)를 참고하세요.

### 빠른 시작

1. 프로젝트 루트의 `plugins/` 안에 폴더 생성
2. `ImervuePlugin`을 상속하는 클래스 정의
3. `__init__.py`에서 `plugin_class = YourPlugin`으로 등록
4. Imervue 재시작

### 훅

| 훅 | 트리거 |
|------|---------|
| `on_plugin_loaded()` | 플러그인 인스턴스화 후 |
| `on_plugin_unloaded()` | 앱 종료 시 |
| `on_build_menu_bar(menu_bar)` | 기본 메뉴 바가 빌드된 후 |
| `on_build_main_tabs(tabs)` | 내장 4개 탭이 추가된 후 |
| `on_build_context_menu(menu, viewer)` | 우클릭 메뉴 열릴 때 |
| `on_image_loaded(path, viewer)` | 딥 줌에서 이미지 로드 후 |
| `on_folder_opened(path, images, viewer)` | 그리드에서 폴더 열린 후 |
| `on_image_switched(path, viewer)` | 이미지 간 내비게이션 시 |
| `on_image_deleted(paths, viewer)` | 이미지(들)이 소프트 삭제된 후 |
| `on_key_press(key, modifiers, viewer)` | 키 누름 시 (이벤트 소비 시 True 반환) |
| `on_app_closing(main_window)` | 애플리케이션 종료 전 |
| `get_translations()` | i18n 문자열 제공 |

### 플러그인 다운로더

**Plugins > Download Plugins**가 온라인 다운로더를 엽니다. 소스 리포지토리: [Jeffrey-Plugin-Repos/Imervue_Plugins](https://github.com/Jeffrey-Plugin-Repos/Imervue_Plugins).

---

## MCP 서버

Imervue는 [Model Context Protocol](https://modelcontextprotocol.io) 서버를 내장하여, AI 어시스턴트(Claude Code / Desktop, Cursor, Cline 등)가 GUI를 띄우지 않고도 프로젝트의 순수 로직 헬퍼를 호출할 수 있게 합니다. Qt 없이 명령 한 줄로:

```sh
python -m Imervue.mcp_server
```

### 도구

| 도구 | 용도 |
|------|---------|
| `list_images` | 폴더의 이미지 파일 목록 (재귀 옵션) |
| `read_image_metadata` | 크기, 포맷, EXIF, XMP 사이드카 |
| `read_xmp_tags` | XMP 전용 빠른 경로: 별점, 라벨, 키워드 |
| `convert_format` | PNG / JPEG / WebP / TIFF / BMP 간 변환 |
| `puppet_from_png` | PNG에서 `.puppet` 리그 빌드 (auto-mesh + 표준 파라미터) |
| `puppet_inspect` | `.puppet`을 열고 인벤토리 반환 |

### 연결

리포지토리 루트에는 Claude Code 자동 탐지를 위한 `.mcp.json`이 포함되어 있습니다. Desktop / 다른 클라이언트의 경우 `claude_desktop_config.json`(또는 동등한 파일)에 다음을 추가하세요:

```json
{
  "mcpServers": {
    "imervue": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "Imervue.mcp_server"]
    }
  }
}
```

전체 프로토콜 표면은 [docs/en/index.rst](../docs/en/index.rst)의 MCP 섹션에 있습니다.

---

## 다국어 지원

| 언어 | 코드 |
|----------|------|
| English | `English` |
| 繁體中文 (Traditional Chinese) | `Traditional_Chinese` |
| 简体中文 (Simplified Chinese) | `Chinese` |
| 한국어 (Korean) | `Korean` |
| 日本語 (Japanese) | `Japanese` |

**Language** 메뉴에서 변경합니다. 재시작이 필요합니다.

플러그인은 `language_wrapper.register_language()`를 통해 완전히 새로운 언어를 등록하거나 `get_translations()`를 통해 번역을 기여할 수 있습니다. [PLUGIN_DEV_GUIDE.md](../PLUGIN_DEV_GUIDE.md#internationalization-i18n)를 참조하세요.

---

## 사용자 설정

작업 디렉터리의 `user_setting.json`에 저장됩니다. 주요 항목:

| 설정 | 타입 | 설명 |
|---------|------|-------------|
| `language` | string | 현재 언어 코드 |
| `user_recent_folders` / `user_recent_images` | list | 최근 열기 |
| `user_last_folder` | string | 시작 시 자동 복원 |
| `bookmarks` | list | 북마크된 이미지 경로 (최대 5000) |
| `sort_by` / `sort_ascending` | string / bool | 정렬 방법 + 순서 |
| `image_ratings` / `image_favorites` / `image_color_labels` | dict / set / dict | 이미지별 정리 |
| `thumbnail_size` / `tile_padding` | int | 그리드 구성 |
| `navigation_auto_loop` | bool | 폴더 끝에서 순환 |
| `keyboard_shortcuts` | dict | 커스텀 키 바인딩 |
| `window_geometry` / `window_state` / `window_maximized` | string / string / bool | 레이아웃 영속화 |
| `stack_raw_jpeg_pairs` | bool | RAW+JPEG 스택 토글 |
| `external_editors` | list | 구성된 편집기 |
| `macros` / `macro_last_name` | list / string | 저장된 매크로 + Alt+M 대상 |

---

## 아키텍처

```
Imervue/
├── __main__.py              # 애플리케이션 진입점
├── Imervue_main_window.py   # 메인 윈도우 (QMainWindow) — 4개 탭 마운트
├── gpu_image_view/          # IMERVUE TAB — GPU 뷰어 + 딥 줌
├── gui/                     # 다이얼로그와 사이드 패널 (현상, EXIF 등)
├── paint/                   # PAINT TAB — 본격 래스터 편집기
├── puppet/                  # PUPPET TAB — 2D 리그드 퍼펫 애니메이터
├── export/                  # 내보내기 생성기 (컨택트 시트, 웹 갤러리, MP4)
├── image/                   # 이미지 유틸리티 (피라미드, 타일 관리자, 정보)
├── library/                 # 라이브러리 헬퍼 (RAW+JPEG 스택, 인덱싱)
├── macros/                  # 매크로 녹화 / 재생
├── menu/                    # 메뉴 정의 (file / tools / filter / …)
├── mcp_server/              # Model Context Protocol stdio 서버
├── multi_language/          # i18n (en / zh-tw / zh-cn / ja / ko)
├── external/                # 외부 편집기 통합
├── plugin/                  # 플러그인 시스템 (base / manager / downloader)
├── sessions/                # 워크스페이스 직렬화
├── system/                  # Windows 파일 연결
└── user_settings/           # 영구 사용자 구성
```

### 렌더링 파이프라인 (Imervue 탭)

1. `GPUImageView`는 `QOpenGLWidget`을 확장
2. 두 개의 GLSL 1.20 프로그램 (textured quads + 단색 사각형)
3. LRU 텍스처 캐시 — 256 타일 한도, 1.5 GB VRAM 예산
4. 512 × 512 타일 크기로 LANCZOS를 사용해 빌드된 다단계 타일 피라미드
5. 하드웨어가 지원할 때 최대 8× 이방성 필터링
6. 셰이더 컴파일 실패 시 소프트웨어 렌더링 대체

### 썸네일 캐시

- **키**: `{path}|{mtime_ns}|{file_size}|{thumbnail_size}`의 MD5
- **포맷**: 압축 PNG (`compress_level=1` — 빠른 쓰기, 작은 풋프린트)
- **위치**: `%LOCALAPPDATA%/Imervue/cache/thumbnails` (Win) 또는 `~/.cache/imervue/thumbnails` (Linux/macOS)
- **무효화**: 파일 메타데이터 변경 시 자동

### Puppet 렌더링 (Puppet 탭)

- `QOpenGLWidget`에 `glDrawElements` + 클라이언트측 vertex 배열
- drawable별: rest vertex를 float32 numpy로 캐시; vertex morph 벡터화; 토폴로지 디포머 정렬을 drawable별 루프 밖으로 호이스트
- 투명도 배경은 2×2 GL_REPEAT 타일링 텍스처 (최적화 이전에는 10만+ immediate-mode quads)
- Cubism 컨버터는 vertex-morph 델타와 함께 opacity_keys 커브를 생성하므로 파라미터 구동 가시성 전환이 `.moc3 → .puppet` 변환 후에도 살아남음

---

## 라이선스

이 프로젝트는 [MIT License](../LICENSE) 하에 라이선스됩니다.

Copyright (c) 2026 JE-Chen
