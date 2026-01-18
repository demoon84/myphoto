import { contextBridge, ipcRenderer } from 'electron'
import { exposeElectronAPI } from '@electron-toolkit/preload'

// Custom APIs for renderer
const api = {
    selectDirectory: () => ipcRenderer.invoke('select-directory'),
    selectFiles: () => ipcRenderer.invoke('select-files'),
    initializeAi: () => ipcRenderer.invoke('initialize-ai'),
    scanFiles: (source: string | string[], dest: string) => ipcRenderer.invoke('scan-files', source, dest),
    pauseProcess: () => ipcRenderer.invoke('pause-process'),
    resumeProcess: () => ipcRenderer.invoke('resume-process'),
    classifyImages: (dest: string) => ipcRenderer.invoke('classify-images', dest),
    pauseAi: () => ipcRenderer.invoke('pause-ai'),
    resumeAi: () => ipcRenderer.invoke('resume-ai'),
    stopAi: () => ipcRenderer.invoke('stop-ai'),
    faceCluster: (dest: string) => ipcRenderer.invoke('face-cluster', dest),
    stopProcess: () => ipcRenderer.invoke('stop-process'),
    cleanupDb: (dest: string) => ipcRenderer.invoke('cleanup-db', dest)
}

// Use `contextBridge` APIs to expose Electron APIs to
// renderer only if context isolation is enabled, otherwise
// just add to the DOM global.
if (process.contextIsolated) {
    try {
        exposeElectronAPI()
        contextBridge.exposeInMainWorld('api', api)
    } catch (error) {
        console.error(error)
    }
} else {
    // @ts-ignore (define in dts)
    window.electron = electronAPI
    // @ts-ignore (define in dts)
    window.api = api
}
