# GitHub 배포 및 릴리스 가이드

MyPhoto 앱을 GitHub에 올리고, 다른 사람들이 DMG 파일을 다운로드할 수 있도록 릴리스(Release)하는 방법입니다.

## 1. 프로젝트를 GitHub에 업로드하기 (최초 1회)

아직 GitHub에 리포지토리(저장소)를 만들지 않았다면 다음 순서로 진행하세요.

1.  **GitHub 웹사이트**에서 로그인 후 [New Repository](https://github.com/new) 버튼을 클릭합니다.
2.  **Repository name**에 `myphoto` (또는 원하는 이름)를 입력합니다.
3.  **Public** (공개) 또는 **Private** (비공개)를 선택합니다. (공개로 해야 다른 사람들이 무료로 다운로드 가능)
4.  **Create repository** 버튼을 클릭합니다.
5.  생성된 페이지에서 `https://github.com/사용자명/myphoto.git` 주소를 복사합니다.

### 터미널에서 업로드 명령어 실행

VS Code 하단 터미널을 열고(`Ctrl + ` `) 다음 명령어들을 순서대로 입력하세요:

```bash
# 1. 깃 저장소 초기화 (이미 되어 있다면 생략 가능하지만 안전을 위해 실행)
git init

# 2. 모든 변경사항 스테이징
git add .

# 3. 커밋 생성
git commit -m "Initial release v1.0.0: AI engine offline mode & packaging fix"

# 4. 방금 만든 GitHub 리포지토리와 연결 (주소는 본인 것으로 변경 필수!)
# git remote add origin https://github.com/YOUR_USERNAME/myphoto.git
# (이미 remote가 있다면 'git remote set-url origin ...' 사용)

# 5. 메인 브랜치로 설정하고 푸시
git branch -M main
git push -u origin main
```

## 2. GitHub Releases에 설치 파일(DMG) 올리기

사람들이 소스 코드가 아닌 **설치 파일(.dmg)**을 쉽게 다운로드하려면 'Releases' 기능을 사용해야 합니다.

1.  GitHub 리포지토리 메인 페이지로 이동합니다.
2.  우측 사이드바(또는 상단 탭)에서 **"Releases"** 섹션을 찾습니다.
3.  **"Create a new release"** (또는 "Draft a new release") 링크를 클릭합니다.
4.  작성 화면에서 다음 내용을 채웁니다:
    *   **Choose a tag**: `v1.0.0` (새로 만들기)
    *   **Target**: `main`
    *   **Release title**: `MyPhoto v1.0.0 - AI 자동 사진 분류기`
    *   **Description**:
        ```markdown
        MyPhoto의 첫 번째 공식 릴리스입니다!
        
        ### 주요 기능
        - 📂 **자동 분류**: 사진을 날짜별, 인물/음식/기타로 자동 정리
        - 🧠 **AI 엔진 탑재**: 인터넷 연결 없이 동작하는 오프라인 AI
        - ⚡ **빠른 속도**: 네이티브 Python 실행 최적화
        
        ### 설치 방법 (macOS)
        1. 아래 Assets 항목에서 `MyPhoto-1.0.0-arm64.dmg`를 다운로드합니다.
        2. 파일을 열고 MyPhoto 아이콘을 Applications 폴더로 드래그합니다.
        3. 최초 실행 시 보안 경고가 뜨면 "시스템 설정 > 개인정보 보호 및 보안"에서 "확인 없이 열기"를 클릭해주세요.
        ```
5.  **Attach binaries by dropping them here** 영역에 방금 빌드한 DMG 파일을 드래그해서 놓습니다.
    *   **파일 위치**: 이 프로젝트 폴더 안의 `dist/MyPhoto-1.0.0-arm64.dmg`
    *   *(파인더에서 찾기 힘들면 터미널에 `open dist`를 입력하세요)*
6.  업로드가 완료되면 **"Publish release"** 버튼을 클릭합니다.

## 3. 다운로드 링크 공유하기

이제 릴리스 페이지 URL을 친구들에게 공유하면 됩니다!
방문자들은 **Assets** 섹션을 열어 `.dmg` 파일을 받아 설치할 수 있습니다.

---
**참고**: macOS 개발자 인증서 서명을 하지 않았으므로, 다른 PC에서 실행 시 "확인되지 않은 개발자" 경고가 뜰 수 있습니다. (설치 방법 3번 참고)
