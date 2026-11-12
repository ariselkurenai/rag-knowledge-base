# 思政案例研习系统 - 一键启动前后端
# 用法：右键"使用 PowerShell 运行"，或在终端执行 .\start.ps1
# 停止：在两个服务窗口中各按 Ctrl+C，或直接关闭窗口

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot

function Test-Port([int]$Port) {
    # 轻量端口探测：Vite 只绑 IPv6(::1)、uvicorn 只绑 IPv4(127.0.0.1)，
    # IPv6 地址必须用 InterNetworkV6 地址族的 socket 才能连上
    foreach ($addr in @("127.0.0.1", "::1")) {
        if ($addr -eq "::1") {
            $tcp = New-Object System.Net.Sockets.TcpClient([System.Net.Sockets.AddressFamily]::InterNetworkV6)
        } else {
            $tcp = New-Object System.Net.Sockets.TcpClient
        }
        try {
            $tcp.ConnectAsync($addr, $Port).Wait(300) | Out-Null
            if ($tcp.Connected) { return $true }
        } catch { } finally { $tcp.Dispose() }
    }
    return $false
}

function Write-Info($msg)  { Write-Host "[启动] $msg" -ForegroundColor DarkCyan }
function Write-Ok($msg)    { Write-Host "[ OK ] $msg" -ForegroundColor Green }
function Write-Skip($msg)  { Write-Host "[跳过] $msg" -ForegroundColor Yellow }

Write-Host ""
Write-Host "==== 高校思政课程案例研习系统 一键启动 ====" -ForegroundColor DarkRed
Write-Host ""

# ── 0) 环境检查 ──────────────────────────────────────────
if (-not (Test-Path "$Root\.env")) {
    Write-Host "[错误] 缺少 $Root\.env（密钥与数据库配置），参考 .env.example 创建后再运行" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path "$Root\rag_env\Scripts\python.exe")) {
    Write-Host "[错误] 缺少 rag_env 虚拟环境（rag_env\Scripts\python.exe）" -ForegroundColor Red
    exit 1
}

# ── 1) 后端（FastAPI :8000）──────────────────────────────
if (Test-Port 8000) {
    Write-Skip "端口 8000 已被占用，后端已在运行"
} else {
    Write-Info "启动后端 FastAPI（http://127.0.0.1:8000，接口文档 /docs）"
    # 直接用 venv 的 python，不依赖 Activate.ps1（避免执行策略限制）
    Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", `
        "cd '$Root'; Write-Host '后端启动中…（Ctrl+C 停止）' -ForegroundColor DarkCyan; & '$Root\rag_env\Scripts\python.exe' -X utf8 -m rag.server"
    $ready = $false
    foreach ($i in 1..30) {
        Start-Sleep -Seconds 1
        if (Test-Port 8000) { $ready = $true; break }
    }
    if ($ready) { Write-Ok "后端已就绪" }
    else        { Write-Host "[警告] 后端 30 秒内未就绪，请查看后端窗口报错（常见：MySQL 未启动 / .env 配置错误）" -ForegroundColor Yellow }
}

# ── 2) 前端（Vite :5173）─────────────────────────────────
if (Test-Port 5173) {
    Write-Skip "端口 5173 已被占用，前端已在运行"
} else {
    if (-not (Test-Path "$Root\frontend\node_modules")) {
        Write-Info "首次运行：安装前端依赖（npm install）"
        Push-Location "$Root\frontend"; npm install; Pop-Location
    }
    Write-Info "启动前端 Vite（http://localhost:5173）"
    Start-Process -FilePath "powershell" -ArgumentList "-NoExit", "-Command", `
        "cd '$Root\frontend'; Write-Host '前端启动中…（Ctrl+C 停止）' -ForegroundColor DarkCyan; npm run dev"
    $ready = $false
    foreach ($i in 1..20) {
        Start-Sleep -Seconds 1
        if (Test-Port 5173) { $ready = $true; break }
    }
    if ($ready) { Write-Ok "前端已就绪" }
    else        { Write-Host "[警告] 前端 20 秒内未就绪，请查看前端窗口报错" -ForegroundColor Yellow }
}

# ── 3) 完成 ─────────────────────────────────────────────
Write-Host ""
Write-Ok "启动完成"
Write-Host "  前端：http://localhost:5173     （在服务窗口 Ctrl+C 停止）"
Write-Host "  后端：http://127.0.0.1:8000/docs（接口文档）"
Write-Host "  演示账号：teacher / 123456（教师）· admin / 123456（管理员）"
Write-Host ""
$open = Read-Host "是否在浏览器打开系统？(回车打开 / 输入 n 跳过)"
if ($open -ne "n") { Start-Process "http://localhost:5173" }
