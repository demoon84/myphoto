import { ipcMain, dialog } from 'electron'
import { spawn } from 'child_process'
import path from 'path'
import { app } from 'electron'
import fs from 'fs'

// Path Resolution Helpers
const isPackaged = app.isPackaged
let pythonPath = ''
let backendPath = ''
let sitePackagesPath = ''

if (process.platform === 'win32') {
    pythonPath = path.join(app.getAppPath(), 'backend', 'venv', 'Scripts', 'python.exe')
    backendPath = path.join(app.getAppPath(), 'backend')
    sitePackagesPath = path.join(backendPath, 'venv', 'Lib', 'site-packages')
} else {
    // macOS/Linux
    if (isPackaged) {
        // When using asarUnpack: ["backend/**/*"], the files are in app.asar.unpacked
        // processing.resourcesPath is .../Contents/Resources
        // app.getAppPath() is .../Contents/Resources/app.asar

        // Correct path for unpacked backend
        const unpackedBackend = path.join(process.resourcesPath, 'app.asar.unpacked', 'backend')

        if (fs.existsSync(unpackedBackend)) {
            backendPath = unpackedBackend
        } else {
            // Fallback (e.g. extraResources)
            const resourcesBackend = path.join(process.resourcesPath, 'backend')
            if (fs.existsSync(resourcesBackend)) {
                backendPath = resourcesBackend
            } else {
                // Fallback to standard
                backendPath = path.join(app.getAppPath(), 'backend')
            }
        }

        // CRITICAL FIX: Use system python on macOS to avoid signature/crash issues with bundled python binary
        if (process.platform === 'darwin') {
            pythonPath = '/usr/bin/python3'
        } else {
            pythonPath = path.join(backendPath, 'venv', 'bin', 'python3')
        }

        // Always point to bundled site-packages
        sitePackagesPath = path.join(backendPath, 'venv', 'lib', 'python3.9', 'site-packages')

    } else {
        // Dev Mode
        backendPath = path.join(app.getAppPath(), 'backend')
        pythonPath = path.join(backendPath, 'venv', 'bin', 'python3')
        sitePackagesPath = path.join(backendPath, 'venv', 'lib', 'python3.9', 'site-packages')
    }
}

let currentPythonProcess: any = null
let aiEngineProcess: any = null

export function setupIpc(mainWindow: Electron.BrowserWindow) {
    // Helper to safely register handler
    const safeHandle = (channel: string, listener: (event: Electron.IpcMainInvokeEvent, ...args: any[]) => (Promise<any>) | (any)) => {
        ipcMain.removeHandler(channel)
        ipcMain.handle(channel, listener)
    }

    safeHandle('select-directory', async () => {
        const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
            properties: ['openDirectory']
        })
        if (canceled) {
            return null
        } else {
            return filePaths[0]
        }
    })

    safeHandle('select-files', async () => {
        const { canceled, filePaths } = await dialog.showOpenDialog(mainWindow, {
            properties: ['openFile', 'multiSelections']
        })
        if (canceled) {
            return null
        } else {
            return filePaths
        }
    })

    safeHandle('scan-files', async (_, source: string | string[], destPath: string) => {
        const dbPath = path.join(destPath, 'myphoto.db')
        const scannerScript = path.join(backendPath, 'scanner.py')

        if (currentPythonProcess) {
            currentPythonProcess.kill()
            currentPythonProcess = null
        }

        let sourceArg: string
        if (Array.isArray(source)) {
            // It's a list of files, write to temp json
            const tempFile = path.join(app.getPath('userData'), 'scan_file_list.json')
            fs.writeFileSync(tempFile, JSON.stringify(source))
            sourceArg = tempFile
        } else {
            // It's a directory path
            sourceArg = source
        }

        console.log(`[IPC] Spawning scanner: ${pythonPath} ${scannerScript}`)
        console.log(`[IPC] PYTHONPATH: ${sitePackagesPath}`)
        mainWindow.webContents.send('error-log', `[시스템] 스캔 프로세스 시작: ${scannerScript}`)

        const pythonProcess = spawn(pythonPath, ['-u', scannerScript, sourceArg, destPath, dbPath], {
            env: { ...process.env, PYTHONPATH: sitePackagesPath }
        })
        currentPythonProcess = pythonProcess

        // Handle Spawn Errors
        pythonProcess.on('error', (err) => {
            const msg = `Failed to start scanner process: ${err.message}`
            console.error(msg)
            mainWindow.webContents.send('error-log', `[치명적 오류] 프로세스 실행 실패: ${err.message} (Path: ${pythonPath})`)
        })

        let newImagesCount = 0
        pythonProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n')
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const status = JSON.parse(line)
                        mainWindow.webContents.send('scanner-status', status)
                        if (status.status === 'completed' && status.new_images !== undefined) {
                            newImagesCount = status.new_images
                        }
                    } catch (e) {
                        console.error('Failed to parse python output:', line)
                    }
                }
            }
        })

        pythonProcess.stderr.on('data', (data) => {
            const errorMsg = data.toString()
            console.error(`Python Error: ${errorMsg}`)
            mainWindow.webContents.send('error-log', errorMsg)
        })

        return new Promise((resolve) => {
            pythonProcess.on('close', (code) => {
                resolve({ success: code === 0, newImages: newImagesCount })
            })
            // If spawn failed, close might not fire or code might be null/non-zero? 
            // Usually 'error' is emitted and then 'close' might not happen or happens with error. 
            // We should ensure we resolve false on error. 
            // But we can't easily resolve the promise from the error handler outside this scope without storing reject.
            // However, typical spawn error flow: 'error' event -> process not started. Close event usually NOT emitted if spawn fails synchronously/immediately.
            // If it fails, the Promise hangs. We need to handle this.
        })
    })


    safeHandle('initialize-ai', async () => {
        const classifierScript = path.join(backendPath, 'classifier.py')

        if (!aiEngineProcess || aiEngineProcess.exitCode !== null) {
            console.log("Pre-starting AI Engine in Service Mode...")
            const pythonProcess = spawn(pythonPath, ['-u', classifierScript, '--mode', 'service'], {
                env: { ...process.env, PYTHONPATH: sitePackagesPath, PYTHONWARNINGS: 'ignore' }
            })
            aiEngineProcess = pythonProcess

            pythonProcess.on('error', (err) => {
                const msg = `Failed to start AI process: ${err.message}`
                console.error(msg)
                mainWindow.webContents.send('error-log', `[치명적 오류] AI 프로세스 실행 실패: ${err.message}`)
            })

            pythonProcess.stdout.on('data', (data) => {
                const lines = data.toString().split('\n')
                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const status = JSON.parse(line)
                            mainWindow.webContents.send('classifier-status', status)
                            pythonProcess.emit('json-message', status)
                        } catch (e) {
                            console.log('AI Log:', line)
                        }
                    }
                }
            })

            pythonProcess.stderr.on('data', (data) => {
                const msg = data.toString()
                if (!msg.includes('GL version') && !msg.includes('gl_context') && !msg.includes('Metal')) {
                    console.error(`AI Engine Error: ${msg}`)
                }
            })
            return true
        }
        return false
    })

    safeHandle('classify-images', async (_, destPath: string) => {
        const dbPath = path.join(destPath, 'myphoto.db')
        const classifierScript = path.join(backendPath, 'classifier.py')

        // Start Persistent Engine if not running
        if (!aiEngineProcess || aiEngineProcess.exitCode !== null) {
            console.log("Starting AI Engine in Service Mode (On-demand)...")
            const pythonProcess = spawn(pythonPath, ['-u', classifierScript, '--mode', 'service'], {
                env: { ...process.env, PYTHONPATH: sitePackagesPath, PYTHONWARNINGS: 'ignore' }
            })
            aiEngineProcess = pythonProcess

            pythonProcess.stdout.on('data', (data) => {
                const lines = data.toString().split('\n')
                for (const line of lines) {
                    if (line.trim()) {
                        try {
                            const status = JSON.parse(line)
                            mainWindow.webContents.send('classifier-status', status)
                            pythonProcess.emit('json-message', status)
                        } catch (e) {
                            console.log('AI Log:', line)
                        }
                    }
                }
            })

            pythonProcess.stderr.on('data', (data) => {
                const msg = data.toString()
                if (!msg.includes('GL version') && !msg.includes('gl_context') && !msg.includes('Metal')) {
                    console.error(`AI Engine Error: ${msg}`)
                }
            })
        }

        // Return a promise that waits for completion
        return new Promise((resolve) => {
            if (!aiEngineProcess) {
                return resolve({ success: false, message: 'Process failed to start' })
            }

            const cleanup = () => {
                aiEngineProcess?.removeListener('json-message', messageHandler)
            }

            const messageHandler = (status: any) => {
                if (status.status === 'completed') {
                    cleanup()
                    resolve({ success: true, peopleCount: status.people_count })
                } else if (status.status === 'error') {
                    cleanup()
                    resolve({ success: false, message: status.message })
                }
            }

            aiEngineProcess.on('json-message', messageHandler)

            const command = JSON.stringify({
                action: 'classify',
                dest: destPath,
                db: dbPath,
                model: 'tf'
            }) + '\n'

            try {
                aiEngineProcess.stdin.write(command)
            } catch (e) {
                cleanup()
                resolve({ success: false, message: 'Failed to write to process' })
            }
        })
    })

    safeHandle('face-cluster', async (_, destPath: string) => {
        const dbPath = path.join(destPath, 'myphoto.db')
        const clusterScript = path.join(backendPath, 'face_cluster.py')

        if (currentPythonProcess) {
            currentPythonProcess.kill()
            currentPythonProcess = null
        }

        const pythonProcess = spawn(pythonPath, ['-u', clusterScript, destPath, dbPath], {
            env: { ...process.env, PYTHONPATH: sitePackagesPath }
        })
        currentPythonProcess = pythonProcess

        pythonProcess.stdout.on('data', (data) => {
            const lines = data.toString().split('\n')
            for (const line of lines) {
                if (line.trim()) {
                    try {
                        const status = JSON.parse(line)
                        mainWindow.webContents.send('cluster-status', status)
                    } catch (e) {
                        // ignore partial json
                    }
                }
            }
        })

        return new Promise((resolve) => {
            pythonProcess.on('close', (code) => {
                currentPythonProcess = null
                resolve({ success: code === 0 })
            })
        })
    })

    safeHandle('cleanup-db', async (_, destPath: string) => {
        const filesToDelete = ['myphoto.db', 'myphoto.db-wal', 'myphoto.db-shm']

        // Try to kill any orphan python processes that might be locking the DB
        try {
            if (process.platform === 'darwin' || process.platform === 'linux') {
                spawn('pkill', ['-f', 'scanner.py'])
                // We DON'T kill aiEngineProcess here as it's a persistent service, 
                // but we trust it closed its connection in 'finally' block.
            }
        } catch (e) { /* ignore */ }

        for (let i = 0; i < 10; i++) { // Increased retries
            try {
                let allDeleted = true
                for (const file of filesToDelete) {
                    const filePath = path.join(destPath, file)
                    if (fs.existsSync(filePath)) {
                        try {
                            fs.unlinkSync(filePath) // Use sync for more immediate feedback
                        } catch (e) {
                            allDeleted = false
                            console.error(`Failed to delete ${file}, attempt ${i + 1}: ${e}`)
                        }
                    }
                }

                if (allDeleted) return true
                await new Promise(resolve => setTimeout(resolve, 1000)) // 1s wait
            } catch (error) {
                console.error('Cleanup error:', error)
            }
        }
        return false
    })

    safeHandle('pause-ai', async () => {
        if (aiEngineProcess) {
            aiEngineProcess.stdin.write(JSON.stringify({ action: 'pause' }) + '\n')
            return true
        }
        return false
    })

    safeHandle('resume-ai', async () => {
        if (aiEngineProcess) {
            aiEngineProcess.stdin.write(JSON.stringify({ action: 'resume' }) + '\n')
            return true
        }
        return false
    })

    safeHandle('stop-ai', async () => {
        if (aiEngineProcess) {
            aiEngineProcess.stdin.write(JSON.stringify({ action: 'stop' }) + '\n')
            return true
        }
        return false
    })

    safeHandle('pause-process', async () => {
        if (currentPythonProcess) {
            currentPythonProcess.stdin.write(JSON.stringify({ action: 'pause' }) + '\n')
            return true
        }
        return false
    })

    safeHandle('resume-process', async () => {
        if (currentPythonProcess) {
            currentPythonProcess.stdin.write(JSON.stringify({ action: 'resume' }) + '\n')
            return true
        }
        return false
    })

    safeHandle('stop-process', async () => {
        if (currentPythonProcess) {
            try {
                currentPythonProcess.stdin.write(JSON.stringify({ action: 'stop' }) + '\n')
            } catch (e) {
                currentPythonProcess.kill()
            }
            return true
        }
        return false
    })
}
