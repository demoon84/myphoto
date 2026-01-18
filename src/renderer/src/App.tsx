import React, { useState, useEffect, useRef } from 'react'
import { FolderOpen, Play, Pause, CheckCircle2, FileText, ImageIcon, Loader2, Square, XCircle, Layers, Bell } from 'lucide-react'
import logo from './assets/bi_logo.png'

function App() {
    // Basic Settings
    const [sourcePath, setSourcePath] = useState<string>('')
    const [selectedFiles, setSelectedFiles] = useState<string[] | null>(null)
    const [destPath, setDestPath] = useState<string>('')
    const [modelReady, setModelReady] = useState(true)

    // Parallel State Management
    const [isScanning, setIsScanning] = useState(false)
    const [isScanPaused, setIsScanPaused] = useState(false)
    const [isAiProcessing, setIsAiProcessing] = useState(false)
    const [isAiPaused, setIsAiPaused] = useState(false)
    const [aiQueue, setAiQueue] = useState<string[]>([]) // Stage 2 Queue (DestPaths)

    // Logs & Notifications
    const [logs, setLogs] = useState<string[]>([])
    const [notifications, setNotifications] = useState<string | null>(null)

    // Progress States (Split)
    const [scanProgress, setScanProgress] = useState<{ file: string, type: string } | null>(null)
    const [aiProgress, setAiProgress] = useState<number>(0) // Changed to number for percentage
    const [aiProgressFile, setAiProgressFile] = useState<string>('') // New state for current file
    const [aiTotalCount, setAiTotalCount] = useState<number>(0)
    const [aiProcessedCount, setAiProcessedCount] = useState<number>(0)

    // Queue Processor
    useEffect(() => {
        const processQueue = async () => {
            if (isAiProcessing || aiQueue.length === 0 || isAiPaused) return

            const nextPath = aiQueue[0]
            setIsAiProcessing(true)
            setAiProcessedCount(0)
            setAiProgress(0) // Reset progress for new item

            // Log keeping
            setLogs(prev => [`[시스템] 대기열 작업 시작: AI 분석 (${nextPath})`, ...prev])

            try {
                // Remove from queue immediately or after? Better after successful start to avoid duplication logic issues, 
                // but for React state, slicing now is safer to prevent loop if we depend on aiQueue in dep array.
                // However, we need to be careful not to lose it if it fails. 
                // Let's slice it first.
                setAiQueue(prev => prev.slice(1))

                const classifyResult = await window.api.classifyImages(nextPath)
                if (classifyResult.success) {
                    setLogs(prev => ['[AI] 분석 및 분류 완료.', ...prev])
                    showNotification('AI 분석이 완료되었습니다!')

                    // Cleanup DB after AI is done for this batch
                    const cleanupRes = await window.api.cleanupDb(nextPath)
                    if (cleanupRes) {
                        setLogs(prev => ['[시스템] 정리 완료 (DB 리셋 성공)', ...prev])
                    } else {
                        setLogs(prev => ['[경고] DB 파일 삭제 실패. 수동 삭제가 필요할 수 있습니다.', ...prev])
                    }
                }
            } catch (error) {
                console.error(error)
                setLogs(prev => ['[오류] AI 분석 중 문제 발생', ...prev])
            } finally {
                setIsAiProcessing(false)
                setAiProgressFile('')
                setAiProgress(0)
                setAiTotalCount(0)
                setAiProcessedCount(0)
            }
        }

        processQueue()
    }, [aiQueue, isAiProcessing, isAiPaused]) // Added isAiPaused to dependencies

    // Event Listeners
    useEffect(() => {
        let ignore = false

        const scannerListener = (_event: any, status: any) => {
            if (status.status === 'progress') {
                setScanProgress({ file: status.file, type: status.type })
                setLogs(prev => [`[정리] ${status.file} (${status.type})`, ...prev.slice(0, 50)])
            } else if (status.status === 'skipped') {
                setLogs(prev => [`[스캔] 중복 건너김: ${status.file}`, ...prev.slice(0, 50)])
            } else if (status.status === 'paused') {
                setIsScanPaused(true)
                setLogs(prev => ['[정리] 사진 정리 일시정지', ...prev.slice(0, 50)])
            } else if (status.status === 'resumed') {
                setIsScanPaused(false)
                setLogs(prev => ['[정리] 사진 정리 재개', ...prev.slice(0, 50)])
            }
        }

        const classifierListener = (_event: any, status: any) => {
            if (status.status === 'processing') {
                setAiProgressFile(status.file)
                setAiProgress(status.progress)
                if (status.total) setAiTotalCount(status.total)
                if (status.current) setAiProcessedCount(status.current)

                // Optional: Reduce log spam for AI by only logging key events or reducing frequency
                setLogs(prev => [`[AI] ${status.file} -> ${status.category}`, ...prev.slice(0, 50)])
            } else if (status.status === 'completed') {
                // Handled in processQueue
            } else if (status.status === 'paused') {
                setIsAiPaused(true)
                setLogs(prev => ['[AI] AI 분석이 일시정지되었습니다.', ...prev])
                showNotification('AI 분석이 일시정지되었습니다.')
            } else if (status.status === 'resumed') {
                setIsAiPaused(false)
                setLogs(prev => ['[AI] AI 분석이 재개되었습니다.', ...prev])
                showNotification('AI 분석이 재개되었습니다.')
            } else if (status.status === 'startup') {
                setLogs(prev => ['[AI] AI 모델 로딩 중...', ...prev])
            } else if (status.status === 'ready') {
                setLogs(prev => ['[AI] AI 모델 준비 완료.', ...prev])
            }
        }

        // Pre-initialize AI immediately when app opens
        window.api.initializeAi()
        setLogs(prev => ['[시스템] AI 엔진 부팅 대기 중...', ...prev])

        const errorLogListener = (_event: any, msg: string) => {
            setLogs(prev => [`[오류-상세] ${msg}`, ...prev])
        }

        window.electron.ipcRenderer.on('scanner-status', scannerListener)
        window.electron.ipcRenderer.on('classifier-status', classifierListener)
        window.electron.ipcRenderer.on('error-log', errorLogListener)

        return () => {
            ignore = true
            window.electron.ipcRenderer.removeAllListeners('scanner-status')
            window.electron.ipcRenderer.removeAllListeners('classifier-status')
            window.electron.ipcRenderer.removeAllListeners('error-log')
        }
    }, [])

    const showNotification = (msg: string) => {
        setNotifications(msg)
        setTimeout(() => setNotifications(null), 3000)
    }

    const handleSelectSource = async () => {
        const path = await window.api.selectDirectory()
        if (path) { setSourcePath(path); setSelectedFiles(null); }
    }

    const handleSelectFiles = async () => {
        const files = await window.api.selectFiles()
        if (files && files.length > 0) {
            setSelectedFiles(files)
            if (files.length === 1) {
                // Show single file path (or name if path is too long? Let's show path for consistency with folder select but maybe just name is better for UX? 
                // Previous behavior for folder was full path. Let's try name to be "cleaner" or path? 
                // The user complained about "not what I selected". Full path is unambiguous.
                setSourcePath(files[0])
            } else {
                // Cross-platform filename extraction
                const firstPath = files[0]
                const name = firstPath.split(/[/\\]/).pop()
                setSourcePath(`${name} 외 ${files.length - 1}개 파일`)
            }
        }
    }

    const handleSelectDest = async () => {
        const path = await window.api.selectDirectory()
        if (path) setDestPath(path)
    }


    const handleScanPause = async () => {
        const success = await window.api.pauseProcess()
        if (success) setIsScanPaused(true)
    }

    const handleScanResume = async () => {
        const success = await window.api.resumeProcess()
        if (success) setIsScanPaused(false)
    }

    const handleStartScan = async () => {
        if (!sourcePath || !destPath) return

        // 1. Immediate UI Update (Optimistic)
        setIsScanning(true)
        setIsScanPaused(false)
        setLogs(prev => ['[시스템] 작업 시작 요청됨...', ...prev])

        try {
            // 2. Pre-initialize AI immediately
            setLogs(prev => ['[시스템] AI 엔진 부팅 시작...', ...prev])
            window.api.initializeAi()

            // 3. Then proceed with cleanup
            setLogs(prev => ['[시스템] 이전 데이터 정리 중...', ...prev.slice(0, 50)])
            await window.api.cleanupDb(destPath)

            setLogs(prev => ['[명령] 사진 정리 시작', ...prev])

            const scanSource = selectedFiles ? selectedFiles : sourcePath
            const currentDest = destPath

            const scanResult = await window.api.scanFiles(scanSource, currentDest)

            if (scanResult.success) {
                if (scanResult.newImages > 0) {
                    setLogs(prev => [`[시스템] 1단계 완료. ${scanResult.newImages}장의 새로운 사진이 발견되어 2단계(AI) 대기열에 추가됨.`, ...prev])
                    showNotification('1단계: 사진 정리가 완료되었습니다!')
                    setAiQueue(prev => [...prev, currentDest])
                } else {
                    setLogs(prev => ['[시스템] 정리 완료. 추가된 새로운 사진이 없어 2단계(AI) 분석을 건너뜁니다.', ...prev])
                    showNotification('정리가 이미 완료된 상태입니다.')
                }
            }
        } catch (e: any) {
            console.error(e)
            setLogs(prev => [`[오류] 스캔 중단 또는 에러 발생: ${e.message || e}`, ...prev])
            setIsScanning(false) // Only revert if error
            setScanProgress(null)
        } finally {
            // Don't turn off isScanning here if successful, because we might want to keep the "Stop" button active?
            // Actually, the original logic turned it off in finally. 
            // If scan is done, isScanning should be false.
            setIsScanning(false)
            setScanProgress(null)
        }
    }

    const handlePause = async () => {
        const success = await window.api.pauseAi()
        if (success) setIsAiPaused(true)
    }

    const handleResume = async () => {
        const success = await window.api.resumeAi()
        if (success) setIsAiPaused(false)
    }

    const handleStop = async () => {
        setLogs(prev => ['작업 중지 요청...', ...prev])
        await window.api.stopProcess() // This stops the scanner
        await window.api.stopAi() // This stops the AI process
        setIsScanning(false)
        setIsAiProcessing(false)
        setIsAiPaused(false)
        setAiQueue([])
        setLogs(prev => ['모든 작업이 중지되었습니다. 대기열이 초기화되었습니다.', ...prev])
    }


    return (
        <div className="h-screen bg-slate-100 text-slate-900 px-6 pb-6 font-sans overflow-hidden flex flex-col selection:bg-indigo-100">
            <div className="max-w-screen-lg mx-auto w-full h-full flex flex-col gap-2.5">
                <header className="flex items-center justify-between shrink-0 pt-[42px] pb-2" style={{ WebkitAppRegion: 'drag' } as any}>
                    <div style={{ WebkitAppRegion: 'no-drag' } as any}>
                        <img src={logo} alt="MyPhoto" className="h-7 object-contain" />
                    </div>
                    {/* Dynamic Status Badge (Top Right) */}
                    {(notifications || isAiProcessing) && (
                        <div style={{ WebkitAppRegion: 'no-drag' } as any} className={`flex items-center gap-2 text-xs font-bold px-3 py-1.5 border rounded-full transition-all duration-300
                            ${notifications
                                ? 'bg-blue-600 border-blue-600 text-white'
                                : 'bg-emerald-50 border-emerald-200 text-emerald-700'}`}>

                            {notifications ? (
                                <>
                                    <Bell size={12} fill="currentColor" />
                                    <span>{notifications}</span>
                                </>
                            ) : (
                                <>
                                    <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
                                    <span>AI 분석 중... {aiQueue.length > 0 && `(대기: ${aiQueue.length})`}</span>
                                </>
                            )}
                        </div>
                    )}
                </header>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-5 shrink-0">
                    {/* Input Cards */}
                    <div className="bg-white border border-slate-200 p-5 rounded-2xl space-y-3 hover:border-indigo-300 transition-all group">
                        <div className="flex items-center gap-2.5">
                            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600 group-hover:bg-indigo-100 transition-colors">
                                {selectedFiles ? <ImageIcon size={18} strokeWidth={2.5} /> : <FolderOpen size={18} strokeWidth={2.5} />}
                            </div>
                            <h3 className="font-bold text-slate-800 text-base">원본 위치</h3>
                        </div>
                        <div className="px-3 py-2.5 bg-slate-50 rounded-lg border border-slate-100">
                            <p className={`text-xs font-medium truncate ${sourcePath ? 'text-slate-900' : 'text-slate-400'}`}>
                                {sourcePath || '선택 대기'}
                            </p>
                        </div>
                        <div className="flex gap-2">
                            <button onClick={handleSelectSource} className="flex-1 py-2 bg-white border border-slate-200 hover:border-indigo-200 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg text-xs font-bold transition-all">폴더 선택</button>
                            <button onClick={handleSelectFiles} className="flex-1 py-2 bg-white border border-slate-200 hover:border-indigo-200 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg text-xs font-bold transition-all">파일 선택</button>
                        </div>
                    </div>

                    <div className="bg-white border border-slate-200 p-5 rounded-2xl space-y-3 hover:border-indigo-300 transition-all group">
                        <div className="flex items-center gap-2.5">
                            <div className="p-2 bg-indigo-50 rounded-lg text-indigo-600 group-hover:bg-indigo-100 transition-colors">
                                <CheckCircle2 size={18} strokeWidth={2.5} />
                            </div>
                            <h3 className="font-bold text-slate-800 text-base">저장 폴더</h3>
                        </div>
                        <div className="px-3 py-2.5 bg-slate-50 rounded-lg border border-slate-100">
                            <p className={`text-xs font-medium truncate ${destPath ? 'text-slate-900' : 'text-slate-400'}`}>
                                {destPath || '선택 대기'}
                            </p>
                        </div>
                        <button onClick={handleSelectDest} className="w-full py-2 bg-white border border-slate-200 hover:border-indigo-200 hover:bg-indigo-50 text-slate-700 hover:text-indigo-700 rounded-lg text-xs font-bold transition-all">폴더 선택</button>
                    </div>
                </div>



                {/* Dashboard Area */}
                <div className="flex-1 flex flex-col gap-4 min-h-0">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 h-full min-h-0">

                        {/* Stage 1: Scanner Panel */}
                        <div className={`p-5 rounded-2xl border flex flex-col gap-4 transition-all relative hover:border-emerald-300 group ${isScanning ? 'bg-emerald-50 border-emerald-200 ring-1 ring-emerald-200' : 'bg-white border-slate-200'}`}>
                            <div className="flex items-center justify-between">
                                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${isScanning ? (isScanPaused ? 'bg-amber-400' : 'bg-emerald-500 animate-pulse') : 'bg-slate-300'}`}></div>
                                    1단계: 사진 정리
                                </h3>
                                {isScanning && (
                                    <div className="flex items-center gap-1.5 overflow-hidden font-mono text-[10px] bg-slate-200/50 px-2 py-0.5 rounded text-slate-500 max-w-[140px]">
                                        <span className="shrink-0">수집중:</span>
                                        <span className="truncate">{scanProgress?.file || '...'}</span>
                                    </div>
                                )}
                            </div>

                            <div className="flex-1 flex flex-col justify-center">
                                {isScanning ? (
                                    <div className="space-y-1.5">
                                        <div className="flex justify-between items-end mb-1">
                                            <span className="text-[10px] font-bold text-emerald-600 tracking-tight uppercase">Scanning files</span>
                                            <span className="text-lg font-black text-emerald-700 leading-none">진행 중</span>
                                        </div>
                                        <div className="h-2.5 bg-emerald-100 rounded-full overflow-hidden border border-emerald-200/50">
                                            <div
                                                className={`h-full bg-emerald-500 rounded-full transition-all duration-500 ${isScanPaused ? 'opacity-50 grayscale-[0.5]' : 'animate-pulse'}`}
                                                style={{ width: `100%` }}
                                            />
                                        </div>
                                        <p className="text-[10px] text-emerald-600/70 font-medium">{isScanPaused ? '정리가 일시 정지되었습니다.' : '파일을 분석하여 날짜별로 정리하고 있습니다.'}</p>
                                    </div>
                                ) : (
                                    <div className="text-center py-2">
                                        <p className="text-slate-400 text-xs font-medium">원본 위치와 저장 폴더를 선택해주세요</p>
                                    </div>
                                )}
                            </div>

                            {isScanning ? (
                                <div className="flex gap-2">
                                    {isScanPaused ? (
                                        <button
                                            onClick={handleScanResume}
                                            className="flex-1 py-3 rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 flex items-center justify-center text-xs font-bold transition-colors shadow-sm"
                                        >
                                            <Play size={10} fill="currentColor" className="mr-2" /> 재개하기
                                        </button>
                                    ) : (
                                        <button
                                            onClick={handleScanPause}
                                            className="flex-1 py-3 rounded-xl bg-white border border-amber-200 text-amber-500 hover:bg-amber-50 hover:text-amber-600 flex items-center justify-center text-xs font-medium transition-colors"
                                        >
                                            <Pause size={10} fill="currentColor" className="mr-2" /> 일시정지
                                        </button>
                                    )}
                                    <button
                                        onClick={handleStop}
                                        className="flex-1 py-3 rounded-xl bg-white border border-rose-200 text-rose-500 hover:bg-rose-50 hover:text-rose-600 flex items-center justify-center text-xs font-medium transition-colors"
                                    >
                                        <Square size={10} fill="currentColor" className="mr-2" /> 중지하기
                                    </button>
                                </div>
                            ) : (
                                <button
                                    onClick={handleStartScan}
                                    disabled={!sourcePath || !destPath || isAiProcessing}
                                    className={`w-full py-3 rounded-2xl flex items-center justify-center text-sm font-bold transition-all active:scale-[0.98] ${(!sourcePath || !destPath || isAiProcessing)
                                        ? 'bg-slate-100 text-slate-400 cursor-not-allowed border border-slate-200'
                                        : 'bg-emerald-500 text-white hover:bg-emerald-600'
                                        }`}
                                >
                                    정리 시작
                                </button>
                            )}
                        </div>

                        {/* Stage 2: AI Panel */}
                        <div className={`p-5 rounded-2xl border flex flex-col gap-4 transition-all relative hover:border-emerald-300 group ${isAiProcessing ? 'bg-emerald-50 border-emerald-200 ring-1 ring-emerald-200' : 'bg-white border-slate-200'}`}>
                            <div className="flex items-center justify-between">
                                <h3 className="font-bold text-slate-800 flex items-center gap-2">
                                    <div className={`w-2 h-2 rounded-full ${isAiProcessing ? (isAiPaused ? 'bg-amber-400' : 'bg-emerald-500 animate-pulse') : 'bg-slate-300'}`}></div>
                                    2단계: AI 분석 및 분류
                                </h3>
                                <div className="flex items-center gap-2">
                                    {aiQueue.length > 0 && (
                                        <span className="text-[10px] font-bold bg-orange-100 text-orange-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                                            <Layers size={10} /> 대기 {aiQueue.length}
                                        </span>
                                    )}
                                    {isAiProcessing && (
                                        <div className="flex items-center gap-1.5 overflow-hidden font-mono text-[10px] bg-slate-200/50 px-2 py-0.5 rounded text-slate-500 max-w-[140px]">
                                            <span className="shrink-0">분석중:</span>
                                            <span className="truncate">{aiProgressFile || '...'}</span>
                                        </div>
                                    )}
                                </div>
                            </div>

                            <div className="flex-1 flex flex-col justify-center">
                                {isAiProcessing ? (
                                    <div className="space-y-1.5">
                                        <div className="flex justify-between items-end mb-1">
                                            <span className="text-[10px] font-bold text-emerald-600 tracking-tight uppercase">Processing images</span>
                                            <span className="text-lg font-black text-emerald-700 leading-none">{aiProgress}%</span>
                                        </div>
                                        <div className="h-2.5 bg-emerald-100 rounded-full overflow-hidden border border-emerald-200/50">
                                            <div
                                                className={`h-full bg-emerald-500 rounded-full transition-all duration-500 ${isAiPaused ? 'opacity-50 grayscale-[0.5]' : 'animate-pulse'}`}
                                                style={{ width: `${aiProgress}%` }}
                                            />
                                        </div>
                                        <p className="text-[10px] text-emerald-600/70 font-medium">{isAiPaused ? '분석이 일시 정지되었습니다.' : '이미지를 분석하고 있습니다.'}</p>
                                    </div>
                                ) : (
                                    <div className="text-center py-2">
                                        <p className="text-slate-400 text-xs font-medium">1단계 완료 후 시작 가능합니다</p>
                                    </div>
                                )}
                            </div>

                            {isAiProcessing ? (
                                <div className="flex gap-2">
                                    {isAiPaused ? (
                                        <button
                                            onClick={handleResume}
                                            className="flex-1 py-3 rounded-xl bg-emerald-500 text-white hover:bg-emerald-600 flex items-center justify-center text-xs font-bold transition-colors shadow-sm"
                                        >
                                            <Play size={10} fill="currentColor" className="mr-2" /> 재개하기
                                        </button>
                                    ) : (
                                        <button
                                            onClick={handlePause}
                                            className="flex-1 py-3 rounded-xl bg-white border border-amber-200 text-amber-500 hover:bg-amber-50 hover:text-amber-600 flex items-center justify-center text-xs font-medium transition-colors"
                                        >
                                            <Pause size={10} fill="currentColor" className="mr-2" /> 일시정지
                                        </button>
                                    )}
                                    <button
                                        onClick={handleStop}
                                        className="flex-1 py-3 rounded-xl bg-white border border-rose-200 text-rose-500 hover:bg-rose-50 hover:text-rose-600 flex items-center justify-center text-xs font-medium transition-colors"
                                    >
                                        <Square size={10} fill="currentColor" className="mr-2" /> 중지하기
                                    </button>
                                </div>
                            ) : (
                                <div className="w-full py-3 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex items-center justify-center text-xs text-slate-400 font-medium">
                                    대기 중
                                </div>
                            )}
                        </div>

                    </div>

                    {/* Console & Stop */}
                    <div className="h-[266px] bg-slate-50/50 rounded-2xl overflow-hidden flex flex-col border border-slate-200 shrink-0 relative mb-4">
                        <div className="bg-slate-100/50 px-5 py-2.5 flex items-center justify-between shrink-0 border-b border-slate-200/60">
                            <div className="flex items-center gap-2">
                                <div className="flex gap-1.5 opacity-40">
                                    <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                                    <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                                    <div className="w-2 h-2 rounded-full bg-slate-400"></div>
                                </div>
                                <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider ml-2">시스템 로그</span>
                            </div>
                        </div>
                        <div className="flex-1 overflow-y-auto px-5 py-3 font-mono text-[11px] space-y-1.5 custom-scrollbar">
                            {logs.map((log, i) => {
                                const isAi = log.includes('[AI]')
                                const isStage1 = log.includes('[정리]') || log.includes('[스캔]') || log.includes('1단계')
                                const isSystem = log.includes('[시스템]') || log.includes('[명령]')

                                return (
                                    <div key={i} className="flex gap-3 opacity-90 hover:opacity-100 transition-opacity">
                                        <span className="text-slate-400 shrink-0 select-none opacity-60">[{new Date().toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' })}]</span>
                                        <span className={`
                                            ${isAi ? 'text-emerald-600 font-medium' :
                                                isStage1 ? 'text-indigo-600' :
                                                    isSystem ? 'text-slate-700 font-bold' :
                                                        'text-slate-500'}
                                        `}>
                                            {log}
                                        </span>
                                    </div>
                                )
                            })}
                            {logs.length === 0 && (
                                <div className="h-full flex items-center justify-center text-slate-300 italic">
                                    현재 기록된 시스템 메세지가 없습니다.
                                </div>
                            )}
                        </div>
                    </div>
                </div>
            </div>
        </div >
    )
}

export default App
