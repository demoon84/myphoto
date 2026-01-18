---
description: 로직 수정 후 앱을 안전하게 종료하고 재시작하는 절차
---

로직 수정이 완료된 후 앱을 재시작해야 할 경우, 다음 단계를 따릅니다.

// turbo-all
1. 실행 중인 Vite 및 Electron 프로세스를 안전하게 종료하여 포트 충돌을 방지합니다.
   `pkill -f "electron-vite" || true && pkill -f "electron" || true && pkill -f "vite" || true`
2. `npm run dev` 명령어를 실행하여 앱을 새로 시동합니다.
