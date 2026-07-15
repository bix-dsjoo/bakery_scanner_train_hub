# Bakery Scanner Train Hub

브랜드별 빵 이미지와 라벨을 관리해 베이커리 스캐너 학습 데이터를 준비하는 내부 도구입니다.

## 현재 단계

현재 저장소는 이미지 관리 MVP의 첫 구현 단계입니다. FastAPI와 React 애플리케이션 기반, 현재 브랜드 선택, 브랜드·상품 등록·수정·비활성화까지 실행할 수 있습니다. 이미지 업로드, 트레이 사진 작업함과 라벨링 편집기는 이후 단계에서 구현합니다.

승인된 상세 설계는 [브랜드별 베이커리 이미지 관리 MVP 설계](docs/superpowers/specs/2026-07-15-bakery-image-management-design.md)에서 확인할 수 있습니다.

구현 기술은 React·TypeScript·FastAPI·Python 3.13·SQLite입니다. UI는 shadcn/ui와 Tailwind CSS 4를 기반으로 BIXOLON 브랜드 색상과 Pretendard를 적용합니다. 현재 개발 환경은 `start-dev.ps1`로 실행하며, 운영용 단일 실행 스크립트와 사내망 배포 검증은 이후 운영 단계에서 완성합니다. 상세한 실행·저장 구조는 [이미지 관리 MVP 기술 설계](docs/superpowers/specs/2026-07-15-image-management-technical-design.md)를 따릅니다.

## 개발 환경 실행

Windows PC에 다음 도구를 먼저 설치하고 각 명령이 PowerShell의 `PATH`에서 실행되는지 확인합니다.

- Python 3.13
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 24 LTS와 npm

저장소 루트에서 다음 명령을 실행합니다.

```powershell
./start-dev.ps1
```

스크립트는 저장소 위치를 기준으로 Python·프런트엔드 의존성을 준비하고, FastAPI reload 서버와 Vite 개발 서버를 함께 시작합니다. 브라우저에서 `http://127.0.0.1:5173`을 열고 종료할 때는 실행 중인 PowerShell에서 `Ctrl+C`를 누릅니다. 관리자 권한이나 방화벽 변경은 필요하지 않습니다.

운영 빌드에서는 FastAPI가 `frontend/dist`의 SPA와 `/api/v1` API를 같은 origin에서 제공합니다. 개발 중에는 Vite가 `/api` 요청을 `http://127.0.0.1:8000`으로 전달합니다.

## 사용자

- 데이터 작업자: 브랜드와 상품을 등록하고 이미지에 정답을 지정합니다.
- ML 엔지니어: 축적된 이미지와 라벨의 구조와 상태를 확인합니다.

MVP는 내부망에서 로그인 없이 사용합니다.

업무 데이터는 기본적으로 `C:\BakeryScannerData`에 저장합니다. MVP에는 자동 백업이 없으므로 PC나 디스크가 고장 나면 데이터를 복구할 수 없습니다.

## MVP가 해결하는 문제

- 브랜드별 상품과 이미지를 분리해 관리합니다.
- 분류기 학습용 상품 사진을 상품에 연결합니다.
- 실제 스캐너 입력과 같은 트레이 사진에서 빵마다 박스를 그리고 상품을 지정합니다.
- 라벨이 필요한 사진과 완료한 사진을 구분합니다.
- 자동 저장과 수정 충돌 감지로 라벨 유실을 방지합니다.

## 이미지 종류

### 상품 사진

빵 하나를 중심으로 촬영한 분류기 학습용 사진입니다. 상품 상세 화면에서 추가하며 현재 상품이 자동으로 연결됩니다.

### 트레이 사진

여러 빵이 함께 놓인 실제 스캐너 입력 형태의 사진입니다. 모든 빵에 박스를 그리고 각 박스에 상품을 지정합니다.

## 인식 모델 방향

초기 인식 파이프라인은 두 단계로 구성합니다.

1. 탐지기가 모든 빵을 `bread` 단일 클래스로 찾습니다.
2. 분류기가 탐지된 박스 영역을 브랜드별 상품으로 분류합니다.

이미지 관리 MVP는 모델을 학습하지 않습니다. 원본 이미지, 박스 좌표, 상품 ID를 모델 중립적인 형태로 보관합니다.

## 대표 작업 흐름

    브랜드 선택
    ├─ 상품 등록 → 상품 사진 추가
    └─ 트레이 사진 업로드
         → 빵마다 박스 생성
         → 박스에 상품 지정
         → 사진 완료
         → 다음 라벨 필요 사진으로 이동

## MVP 범위

포함:

- 브랜드와 상품 관리
- 상품 사진과 트레이 사진 일괄 업로드
- 트레이 사진 바운딩 박스 편집
- 박스별 상품 지정
- `라벨 필요`과 `완료` 상태
- 브랜드, 상품, 상태, 파일명 검색과 필터
- 자동 저장, 중복 이미지 검사, 동시 수정 충돌 감지

제외:

- 모델 학습과 실험 비교
- 데이터셋 버전, 분할, YOLO·COCO 내보내기
- 모델 등록, 승인, 변환, 배포
- 스캐너 단말의 자동 이미지 수집
- 외부 라벨링 도구
- 로그인, 역할별 권한, 별도 검수 단계

## 문서

- [이미지 관리 MVP 설계](docs/superpowers/specs/2026-07-15-bakery-image-management-design.md)
- [이미지 관리 MVP 기술 설계](docs/superpowers/specs/2026-07-15-image-management-technical-design.md)
- [이미지 관리 MVP UI 디자인](docs/superpowers/specs/2026-07-15-image-management-ui-design.md)
- [이미지 관리 MVP 구현 로드맵](docs/superpowers/plans/2026-07-15-image-management-implementation-roadmap.md)
- [문서 기반 구현 계획](docs/superpowers/plans/2026-07-15-documentation-foundation.md)
- [에이전트 작업 지침](AGENTS.md)

## 저장소 상태

현재 구현 범위는 애플리케이션 기반과 브랜드·상품 카탈로그입니다. 이미지 업로드, 라벨링, 운영 배포 기능은 승인된 구현 로드맵의 다음 단계에서 추가합니다.
