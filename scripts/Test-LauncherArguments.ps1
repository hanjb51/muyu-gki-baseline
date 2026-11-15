param([string]$LauncherPath)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([string]::IsNullOrEmpty($LauncherPath)) {
    $LauncherPath = Join-Path (Split-Path -Parent $PSScriptRoot) 'Start-Baseline.ps1'
}
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($LauncherPath, [ref]$tokens, [ref]$errors)
if ($errors.Count -ne 0) { throw 'Launcher parse failed.' }
$functions = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $true)
. ([scriptblock]::Create((($functions | ForEach-Object { $_.Extent.Text }) -join "`n")))
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$ghCommand = $pythonPath
$gitCommand = $pythonPath
$echoCode = 'import sys,json;print(json.dumps(sys.argv[1:],ensure_ascii=True))'

$result = Invoke-GhChecked -GhArguments @('-c',$echoCode,'api','user','--jq','.login')
$observed = ConvertFrom-Json -InputObject ([string]$result)
if ($observed.Count -ne 4 -or ($observed -join '|') -ne 'api|user|--jq|.login') { throw 'GitHub api arguments were not preserved.' }

$message = 'Build pristine muyu 6.1.138 companion GKI with enforced ABI checks'
$helper = 'credential.helper=!gh auth git-credential'
$result = Invoke-GitChecked -GitArguments @('-c',$echoCode,'-c',$helper,'commit','-m',$message)
$observed = ConvertFrom-Json -InputObject ([string]$result)
if ($observed.Count -ne 5 -or $observed[1] -ne $helper -or $observed[4] -ne $message) { throw 'Git message/helper arguments were not preserved.' }

$pathWithSpaces = Join-Path $env:TEMP 'muyu argument transport test'
$result = Invoke-GhChecked -GhArguments @('-c',$echoCode,'repo','clone','owner/repository',$pathWithSpaces,'--','--depth=1')
$observed = ConvertFrom-Json -InputObject ([string]$result)
if ($observed.Count -ne 6 -or $observed[3] -ne $pathWithSpaces) { throw 'Clone path with spaces was not preserved.' }

$caught = $false
try { Invoke-GhChecked -GhArguments @('-c','import sys;sys.exit(7)') } catch { $caught = $true }
if (-not $caught) { throw 'Native nonzero exit was not propagated.' }

$result = Invoke-GhChecked -GhArguments @('-c',"import sys;sys.stderr.write('progress\n');print('OK')")
if ($result -ne 'OK') { throw 'Native stderr polluted API stdout.' }

if (Test-GhResource -GhArguments @('-c',"import sys;sys.stderr.write('expected missing resource');sys.exit(1)")) { throw 'Missing resource probe returned true.' }
if (-not (Test-GhResource -GhArguments @('-c','import sys;sys.exit(0)'))) { throw 'Successful resource probe returned false.' }

$repositoryInfo = ConvertFrom-Json '{"full_name":"hanjb51/muyu-gki-baseline","fork":true,"parent":{"full_name":"Xieansecn/buildGKI-6.1.138-android14"}}'
Assert-DedicatedFork -RepositoryInfo $repositoryInfo -ExpectedName 'hanjb51/muyu-gki-baseline'
$repositoryInfo.parent.full_name = 'unrelated/repository'
$caught = $false
try { Assert-DedicatedFork -RepositoryInfo $repositoryInfo -ExpectedName 'hanjb51/muyu-gki-baseline' } catch { $caught = $true }
if (-not $caught) { throw 'Unrelated repository was not rejected.' }
$caught = $false
try { Assert-DedicatedFork -RepositoryInfo ([pscustomobject]@{ full_name = 'hanjb51/muyu-gki-baseline' }) -ExpectedName 'hanjb51/muyu-gki-baseline' } catch { $caught = $true }
if (-not $caught) { throw 'Incomplete repository response was not rejected.' }

Write-Output ('PASS: ten launcher argument/exit/stream/resource/repository checks; PowerShell ' + $PSVersionTable.PSVersion)
