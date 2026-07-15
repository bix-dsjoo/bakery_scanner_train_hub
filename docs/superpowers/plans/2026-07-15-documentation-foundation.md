# Bakery Scanner Train Hub Documentation Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 승인된 이미지 관리 MVP 설계를 처음 방문한 개발자와 AI 에이전트가 바로 이해할 수 있도록 `README.md`와 루트 `AGENTS.md`로 정리한다.

**Architecture:** `README.md`는 사람을 위한 프로젝트 입구이며 목적, 현재 단계, MVP 범위, 핵심 흐름, 문서 위치를 설명한다. `AGENTS.md`는 저장소 전체에 적용되는 작업 계약으로서 설계 문서를 소스 오브 트루스로 지정하고 데이터 불변식, UI 문구, 테스트, 범위 제한을 강제한다.

**Tech Stack:** Markdown, Git, PowerShell, ripgrep

## Global Constraints

- 소스 오브 트루스는 `docs/superpowers/specs/2026-07-15-bakery-image-management-design.md`다.
- 현재 브랜치에는 실행 가능한 애플리케이션이 없으며 이번 계획은 문서 두 개만 추가한다.
- 초기 사용자는 데이터 작업자와 ML 엔지니어다.
- MVP는 내부망에서 로그인 없이 사용한다.
- 이미지 종류의 사용자 노출 명칭은 `상품 사진`과 `트레이 사진`이다.
- 트레이 이미지 상태의 사용자 노출 명칭은 `라벨 필요`와 `완료`다.
- 탐지기는 모든 빵을 `bread` 단일 클래스로 찾고, 분류기는 박스 영역을 브랜드별 상품으로 분류한다.
- 모델 학습, 데이터셋 분할·내보내기, 모델 관리·배포, 단말 자동 수집, 외부 라벨링, 사용자 권한은 MVP 범위 밖이다.
- 새 문서는 UTF-8 Markdown으로 작성하고 문장 끝의 불필요한 공백을 허용하지 않는다.

---

### Task 1: 프로젝트 입구 README 작성

**Files:**
- Create: `README.md`
- Reference: `docs/superpowers/specs/2026-07-15-bakery-image-management-design.md`

**Interfaces:**
- Consumes: 승인된 설계의 목표, 비목표, 사용자, 2단계 모델 방향, 화면 흐름
- Produces: 사람과 이후 작업자가 프로젝트를 처음 이해할 때 사용하는 루트 `README.md`

- [ ] **Step 1: README가 아직 없음을 확인**

Run:

```powershell
if (Test-Path 'README.md') {
  Write-Error 'README.md already exists; inspect it before applying this task.'
  exit 1
}
Write-Output 'README.md is absent'
```

Expected: `README.md is absent`

- [ ] **Step 2: README 작성**

Create `README.md` with exactly this content:

```markdown
# Bakery Scanner Train Hub

브랜드별 빵 이미지와 라벨을 관리해 베이커리 스캐너 학습 데이터를 준비하는 내부 도구입니다.

## 현재 단계

현재 저장소는 이미지 관리 MVP의 설계를 마친 단계입니다. 실행 가능한 애플리케이션 코드는 아직 없습니다.

승인된 상세 설계는 [브랜드별 베이커리 이미지 관리 MVP 설계](docs/superpowers/specs/2026-07-15-bakery-image-management-design.md)에서 확인할 수 있습니다.

## 사용자

- 데이터 작업자: 브랜드와 상품을 등록하고 이미지에 정답을 지정합니다.
- ML 엔지니어: 축적된 이미지와 라벨의 구조와 상태를 확인합니다.

MVP는 내부망에서 로그인 없이 사용합니다.

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
- [문서 기반 구현 계획](docs/superpowers/plans/2026-07-15-documentation-foundation.md)
- [에이전트 작업 지침](AGENTS.md)

## 저장소 상태

현재 브랜치는 문서 중심의 기획 단계입니다. 애플리케이션 기술 스택과 코드 구조는 별도의 승인된 구현 계획에서 결정합니다.
```

- [ ] **Step 3: README 핵심 내용 검증**

Run:

```powershell
$content = Get-Content -Raw -Encoding UTF8 'README.md'
$required = @(
  '# Bakery Scanner Train Hub',
  '## 현재 단계',
  '## MVP가 해결하는 문제',
  '## 인식 모델 방향',
  '## MVP 범위',
  'docs/superpowers/specs/2026-07-15-bakery-image-management-design.md'
)
$missing = $required | Where-Object { -not $content.Contains($_) }
if ($missing.Count -gt 0) {
  Write-Error ('README missing: ' + ($missing -join ', '))
  exit 1
}
Write-Output 'README verification passed'
```

Expected: `README verification passed`

- [ ] **Step 4: Markdown 공백 검사**

Run:

```powershell
git diff --check -- README.md
```

Expected: exit code 0 with no output

- [ ] **Step 5: README 커밋**

```powershell
git add README.md
git commit -m "docs: add project README"
```

Expected: one commit containing only `README.md`

---

### Task 2: 저장소 전체 AGENTS 지침 작성

**Files:**
- Create: `AGENTS.md`
- Reference: `README.md`
- Reference: `docs/superpowers/specs/2026-07-15-bakery-image-management-design.md`

**Interfaces:**
- Consumes: README의 공개 프로젝트 요약과 승인된 설계의 데이터·UI·테스트 규칙
- Produces: 저장소의 모든 파일과 하위 디렉터리에 적용되는 루트 `AGENTS.md`

- [ ] **Step 1: AGENTS가 아직 없음을 확인**

Run:

```powershell
if (Test-Path 'AGENTS.md') {
  Write-Error 'AGENTS.md already exists; inspect it before applying this task.'
  exit 1
}
Write-Output 'AGENTS.md is absent'
```

Expected: `AGENTS.md is absent`

- [ ] **Step 2: AGENTS 작성**

Create `AGENTS.md` with exactly this content:

```markdown
# AGENTS.md

## 적용 범위

이 파일은 저장소 루트와 모든 하위 디렉터리에 적용됩니다. 더 구체적인 `AGENTS.md`가 하위 디렉터리에 추가되면 해당 범위에서는 하위 지침을 함께 따릅니다.

## 먼저 읽을 문서

작업을 시작하기 전에 다음 순서로 읽습니다.

1. `README.md`
2. `docs/superpowers/specs/2026-07-15-bakery-image-management-design.md`
3. 현재 작업과 관련된 `docs/superpowers/plans/` 아래의 승인된 계획

설계 문서는 제품 범위와 데이터 규칙의 소스 오브 트루스입니다. README나 코드가 설계와 충돌하면 임의로 해석하지 말고 설계를 기준으로 차이를 보고합니다.

## 현재 프로젝트 단계

- 현재 브랜치는 이미지 관리 MVP의 기획·문서화 단계입니다.
- 실행 가능한 애플리케이션 기술 스택은 아직 선택하지 않았습니다.
- 승인된 구현 계획 없이 프레임워크, 데이터베이스, 배포 환경을 임의로 도입하지 않습니다.
- 이번 MVP는 내부망에서 로그인 없이 사용합니다.

## 제품 범위

MVP에 포함되는 기능:

- 브랜드와 상품 관리
- 상품 사진과 트레이 사진 업로드
- 트레이 사진의 바운딩 박스 편집
- 박스별 상품 지정
- `라벨 필요`과 `완료` 상태
- 검색과 필터
- 자동 저장, 중복 검사, 동시 수정 충돌 감지

MVP에 포함되지 않는 기능:

- 모델 학습과 실험 비교
- 데이터셋 버전, 분할, YOLO·COCO 내보내기
- 모델 등록, 승인, ONNX 변환, 단말 배포
- 스캐너 단말의 자동 이미지 수집
- 외부 라벨링 도구 연동
- 로그인, 역할별 권한, 작업 할당, 검수 승인, 감사 로그

범위 밖 기능은 관련 설계와 구현 계획이 별도로 승인되기 전까지 추가하지 않습니다.

## 도메인 용어

- `상품 사진`: 상품 하나와 직접 연결된 분류기 학습용 사진
- `트레이 사진`: 여러 빵이 함께 있으며 빵마다 박스가 필요한 사진
- `박스`: 트레이 사진 속 빵 하나의 정규화된 바운딩 박스
- `라벨 필요`: 트레이 이미지의 `UNLABELED` 상태를 사용자가 보는 명칭
- `완료`: 이미지의 `COMPLETED` 상태를 사용자가 보는 명칭

UI에서 `어노테이션`, `객체 탐지용 이미지`, `레퍼런스 이미지`보다 위 사용자 용어를 우선합니다.

## 모델 방향

- 탐지기는 모든 빵을 `bread` 단일 클래스로 찾습니다.
- 분류기는 탐지된 박스 영역을 브랜드별 상품으로 분류합니다.
- 탐지 학습에서는 저장된 모든 박스를 `bread`로 변환할 수 있어야 합니다.
- 분류 학습에서는 상품 사진과 상품 ID가 지정된 박스 영역을 사용할 수 있어야 합니다.
- 박스 crop은 원본으로 중복 저장하지 않고 데이터셋 생성 시 파생합니다.

## 데이터 불변식

- 상품 코드는 같은 브랜드 안에서 중복될 수 없습니다.
- 같은 브랜드에 같은 SHA-256을 가진 활성 이미지를 중복 등록하지 않습니다.
- 상품 사진은 같은 브랜드의 활성 상품과 함께 등록하며 정상 등록 후 항상 완료 상태입니다.
- 트레이 사진의 `product_id`는 비어 있고 상품은 각 박스에 연결합니다.
- 박스는 트레이 사진에만 생성할 수 있습니다.
- 박스의 상품과 이미지는 같은 브랜드에 속해야 합니다.
- 박스 좌표는 원본 이미지 기준 0 이상 1 이하의 `x1, y1, x2, y2`이며 `x1 < x2`와 `y1 < y2`를 만족해야 합니다.
- 트레이 사진은 박스가 하나 이상 있고 모든 박스에 상품이 지정되어야 완료할 수 있습니다.
- 완료된 트레이 사진에 미지정 박스가 생기거나 모든 박스가 삭제되면 라벨 필요 상태로 돌아갑니다.
- 비활성 상품은 기존 라벨에서 유지하지만 새 박스에는 지정할 수 없습니다.

## UI/UX 규칙

- 한 화면에는 하나의 대표 작업만 둡니다.
- 현재 브랜드 맥락을 유지하고 다른 브랜드의 상품을 선택지에 노출하지 않습니다.
- 상품 상세에서 추가한 사진은 이미지 종류와 상품을 다시 묻지 않습니다.
- 트레이 사진 화면에서 추가한 사진은 이미지 종류를 다시 묻지 않습니다.
- 라벨링 변경은 자동 저장하며 저장 상태를 `저장 중`, `저장됨`, `저장하지 못함`으로 표시합니다.
- 모든 박스가 유효할 때만 `이 사진 완료`를 활성화합니다.
- 완료 후 다음 라벨 필요 이미지로 이동합니다.
- 사용자가 실패 원인과 다음 행동을 알 수 있는 문구를 작성합니다.
- 긴 상품명, 키보드 초점, 브라우저 확대와 다양한 화면 크기를 고려합니다.

## 작업 방식

- 코드 또는 동작 변경 전 승인된 설계와 구현 계획을 확인합니다.
- 기능과 버그 수정은 테스트를 먼저 작성하고 실패를 확인한 뒤 최소 구현으로 통과시킵니다.
- 파일은 한 가지 책임을 갖도록 작게 유지합니다.
- 현재 작업과 무관한 리팩터링과 의존성 추가를 피합니다.
- 기존 사용자 변경을 덮어쓰거나 되돌리지 않습니다.
- 자동 생성 파일보다 사람이 유지해야 하는 원본 파일을 수정합니다.
- 새 결정이 기존 설계를 바꾸면 코드보다 설계 문서를 먼저 갱신하고 승인을 받습니다.

## 테스트 기준

향후 애플리케이션 구현 시 최소한 다음을 자동 검증합니다.

- 상품 사진의 필수 상품 연결
- 트레이 사진 완료 조건과 상태 전이
- 박스 좌표 검증
- 브랜드 간 상품 연결 차단
- 비활성 상품의 신규 지정 차단
- 정상·비정상·중복 이미지 업로드와 부분 실패
- 박스 생성·수정·삭제와 revision 충돌
- 새로고침, 자동 저장 실패, 네트워크 복구
- 마우스와 키보드 기반 라벨링 흐름

완료를 주장하기 전에 관련 테스트와 `git diff --check`를 새로 실행하고 실제 결과를 확인합니다.

## 문서 규칙

- 사용자용 설명은 한국어로 작성하고 코드 식별자와 상태값은 설계의 영문 이름을 유지합니다.
- 날짜가 있는 설계와 계획 파일은 `YYYY-MM-DD-주제.md` 형식을 사용합니다.
- 내용이 비어 있거나 결정을 미룬 미완성 표식을 최종 문서에 남기지 않습니다.
- 로컬 문서 링크는 저장소 루트 기준 상대 경로를 사용합니다.
- 설계와 README의 범위, 용어, 상태명이 항상 일치하는지 확인합니다.

## Git 규칙

- 관련 변경만 스테이징합니다.
- 테스트 또는 검증이 통과한 작은 단위로 커밋합니다.
- 사용자 요청 없이 원격으로 푸시하거나 PR을 만들지 않습니다.
- 강제 푸시, hard reset, 기존 커밋 재작성은 명시적 승인 없이 하지 않습니다.
```

- [ ] **Step 3: AGENTS 핵심 규칙 검증**

Run:

```powershell
$content = Get-Content -Raw -Encoding UTF8 'AGENTS.md'
$required = @(
  '## 적용 범위',
  '## 제품 범위',
  '## 데이터 불변식',
  '## UI/UX 규칙',
  '## 테스트 기준',
  '## Git 규칙',
  'docs/superpowers/specs/2026-07-15-bakery-image-management-design.md',
  '사용자 요청 없이 원격으로 푸시하거나 PR을 만들지 않습니다.'
)
$missing = $required | Where-Object { -not $content.Contains($_) }
if ($missing.Count -gt 0) {
  Write-Error ('AGENTS missing: ' + ($missing -join ', '))
  exit 1
}
Write-Output 'AGENTS verification passed'
```

Expected: `AGENTS verification passed`

- [ ] **Step 4: 문서 간 일관성과 로컬 링크 검증**

Run:

```powershell
$files = @(
  'README.md',
  'AGENTS.md',
  'docs/superpowers/specs/2026-07-15-bakery-image-management-design.md'
)
foreach ($file in $files) {
  if (-not (Test-Path $file)) {
    Write-Error "Missing file: $file"
    exit 1
  }
  $content = Get-Content -Raw -Encoding UTF8 $file
  $unfinishedMarkers = @(
    ('T' + 'BD'),
    ('T' + 'ODO'),
    ('F' + 'IXME'),
    ('place' + 'holder'),
    ('미' + '정'),
    ('추후 ' + '결정'),
    ('나중에 ' + '결정')
  )
  foreach ($marker in $unfinishedMarkers) {
    if ($content.Contains($marker)) {
      Write-Error "Unfinished marker found in $file"
      exit 1
    }
  }
}

$readme = Get-Content -Raw -Encoding UTF8 'README.md'
$agents = Get-Content -Raw -Encoding UTF8 'AGENTS.md'
$terms = @('상품 사진', '트레이 사진', '라벨 필요', '완료', 'bread')
foreach ($term in $terms) {
  if (-not $readme.Contains($term) -or -not $agents.Contains($term)) {
    Write-Error "Inconsistent term: $term"
    exit 1
  }
}

$localLinks = @(
  'docs/superpowers/specs/2026-07-15-bakery-image-management-design.md',
  'docs/superpowers/plans/2026-07-15-documentation-foundation.md',
  'AGENTS.md'
)
foreach ($link in $localLinks) {
  if (-not (Test-Path $link)) {
    Write-Error "Broken local link: $link"
    exit 1
  }
}

git diff --check -- README.md AGENTS.md
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Output 'Cross-document verification passed'
```

Expected: `Cross-document verification passed`

- [ ] **Step 5: AGENTS 커밋**

```powershell
git add AGENTS.md
git commit -m "docs: add repository agent guidance"
```

Expected: one commit containing only `AGENTS.md`

---

## Final Verification

Run:

```powershell
git status --short
git log -3 --oneline
$files = @(
  'README.md',
  'AGENTS.md',
  'docs/superpowers/specs/2026-07-15-bakery-image-management-design.md',
  'docs/superpowers/plans/2026-07-15-documentation-foundation.md'
)
$unfinishedMarkers = @(
  ('T' + 'BD'),
  ('T' + 'ODO'),
  ('F' + 'IXME'),
  ('place' + 'holder'),
  ('미' + '정'),
  ('추후 ' + '결정'),
  ('나중에 ' + '결정')
)
foreach ($file in $files) {
  $content = Get-Content -Raw -Encoding UTF8 $file
  foreach ($marker in $unfinishedMarkers) {
    if ($content.Contains($marker)) {
      Write-Error "Unfinished marker found in $file"
      exit 1
    }
  }
}
Write-Output 'Final documentation verification passed'
```

Expected:

- `git status --short` has no output.
- The latest commits include `docs: add project README` and `docs: add repository agent guidance`.
- The final verification prints `Final documentation verification passed`.
