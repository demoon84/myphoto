/// <reference types="vite/client" />
import { ElectronAPI } from '@electron-toolkit/preload'

declare module '*.png' {
    const value: string;
    export default value;
}

declare global {
    interface Window {
        electron: ElectronAPI
        api: {
            selectDirectory: () => Promise<string | null>
            selectFiles: () => Promise<string[] | null>
            initializeAi: () => Promise<boolean>
            scanFiles: (source: string | string[], dest: string) => Promise<{ success: boolean; newImages: number }>
            pauseProcess: () => Promise<boolean>
            resumeProcess: () => Promise<boolean>
            classifyImages: (dest: string) => Promise<{ success: boolean; message?: string; peopleCount?: number }>
            pauseAi: () => Promise<boolean>
            resumeAi: () => Promise<boolean>
            stopAi: () => Promise<boolean>
            faceCluster: (dest: string) => Promise<{ success: boolean }>
            stopProcess: () => Promise<boolean>
            cleanupDb: (dest: string) => Promise<boolean>
        }
    }
}
