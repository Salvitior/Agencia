$ErrorActionPreference = "Stop"

function Get-WslContext {
    param([string]$Path)

    if ($Path -match '^\\\\wsl\.localhost\\([^\\]+)\\(.+)$') {
        $distro = $Matches[1]
        $linuxPath = "/" + (($Matches[2] -replace '\\', '/') -replace '^/+', '')
        return @{
            Distro = $distro
            LinuxPath = $linuxPath
        }
    }

    $linuxPath = (& wsl.exe wslpath -a ($Path -replace '\\', '/')).Trim()
    return @{
        Distro = $null
        LinuxPath = $linuxPath
    }
}

function Invoke-WslScript {
    param(
        [string]$ScriptName
    )

    $context = Get-WslContext -Path $PSScriptRoot
    $linuxPath = $context.LinuxPath
    $command = "cd '$linuxPath' && chmod +x '$ScriptName' && ./'$ScriptName'"

    if ($context.Distro) {
        & wsl.exe -d $context.Distro bash -lc $command
    } else {
        & wsl.exe bash -lc $command
    }
}

Invoke-WslScript -ScriptName "start_all.sh"
