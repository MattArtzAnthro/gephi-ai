# Gephi AI installer for Windows (Windows PowerShell 5.1 or PowerShell 7).
#
#   irm https://raw.githubusercontent.com/MattArtzAnthro/gephi-ai/main/install.ps1 | iex
#
# With options:
#   & ([scriptblock]::Create((irm https://raw.githubusercontent.com/MattArtzAnthro/gephi-ai/main/install.ps1))) -DryRun
#
#   -Yes               accept every default without asking
#   -DryRun            print what would change and change nothing
#   -Clients LIST      only these, comma-separated: claude,codex,gemini,desktop
#   -SkipGephiPlugin   leave Gephi Desktop alone; connect the assistants only
#   -Version X.Y.Z     install a specific release instead of the latest
#   -OpenGephi         open Gephi at the end and check that the plugin answers
#   -NoLaunch          do not reopen Gephi if the installer had to close it
#   -Uninstall         remove what this script installs (leaves uv and Gephi)
#
# Safe to re-run: it updates what is out of date and skips what is current.
# macOS and Linux: see install.sh in the same repository.

param(
    [switch]$Yes,
    [switch]$DryRun,
    [string[]]$Clients = @(),
    [switch]$SkipGephiPlugin,
    [string]$Version = "",
    [switch]$NoLaunch,
    [switch]$OpenGephi,
    [switch]$Uninstall
)

# Everything lives inside one function so that a failure never runs `exit`,
# which under `irm | iex` would close the user's PowerShell window.
function Install-GephiAI {
    param($Yes, $DryRun, $Clients, $SkipGephiPlugin, $Version, $NoLaunch, $OpenGephi, $Uninstall)

    $ErrorActionPreference = "Stop"
    $ProgressPreference = "SilentlyContinue"  # the progress bar slows downloads tenfold in 5.1
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12

    $Repo = "MattArtzAnthro/gephi-ai"
    $Marketplace = "gephi-ai"
    $Plugin = "gephi-network-analysis@gephi-ai"
    $ModuleBase = "org-gephi-plugins-gephi-ai"
    $LegacyBase = "org-gephi-plugins-gephi-mcp"
    $DownloadPage = "https://gephi.org/desktop/"

    $script:Summary = New-Object System.Collections.Generic.List[string]
    $script:Next = New-Object System.Collections.Generic.List[string]
    $script:Uvx = $null
    $script:Step = "starting"
    $script:ClosedGephi = $false
    $Tmp = Join-Path ([IO.Path]::GetTempPath()) ("gephi-ai-install-" + [guid]::NewGuid().ToString("N").Substring(0, 8))
    New-Item -ItemType Directory -Path $Tmp -Force | Out-Null
    $Log = Join-Path ([IO.Path]::GetTempPath()) ("gephi-ai-install-" + (Get-Date -Format "yyyyMMdd-HHmmss") + ".log")

    # ---------- output ----------

    function Head($t) { $script:Step = $t; Write-Host ""; Write-Host "==> $t" -ForegroundColor White }
    function Ok($t) { Write-Host "  + $t" -ForegroundColor Green }
    function Warn($t) { Write-Host "  ! $t" -ForegroundColor Yellow }
    function Say($t) { Write-Host "  $t" }
    function Done($t) { $script:Summary.Add("[ok]   $t") }
    function Skip($t) { $script:Summary.Add("[skip] $t") }
    function Fail($t) { $script:Summary.Add("[fail] $t"); $script:Failed = $true }

    function Ask($q, $def) {
        if ($Yes -or -not [Environment]::UserInteractive) { return ($def -eq "Y") }
        $hint = if ($def -eq "Y") { "[Y/n]" } else { "[y/N]" }
        $r = Read-Host "  $q $hint"
        if ([string]::IsNullOrWhiteSpace($r)) { $r = $def }
        return ($r -match "^[Yy]")
    }

    function Has($name) { return [bool](Get-Command $name -ErrorAction SilentlyContinue) }

    # Run a command-line tool, showing its output only when it fails. Native
    # programs that write to stderr turn into errors in Windows PowerShell 5.1
    # under "Stop", so relax it around the call. Plain $args, not a param block:
    # a param block would claim flags such as -s or --ref as its own parameters
    # instead of passing them to the tool.
    function Run {
        $exe = $args[0]; $rest = @()
        if ($args.Count -gt 1) { $rest = @($args[1..($args.Count - 1)]) }  # $args[1..0] would count backwards
        $line = $exe + " " + ($rest -join " ")
        if ($DryRun) { Write-Host "  would run: $line" -ForegroundColor DarkGray; return $true }
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { $out = @(& $exe @rest 2>&1 | ForEach-Object { "$_" }) } finally { $ErrorActionPreference = $old }
        if ($LASTEXITCODE -eq 0) { return $true }
        Write-Host "  $ $line" -ForegroundColor DarkGray
        $out | Select-Object -Last 15 | ForEach-Object { Write-Host "    $_" }
        return $false
    }

    function Output-Of {
        $exe = $args[0]; $rest = @()
        if ($args.Count -gt 1) { $rest = @($args[1..($args.Count - 1)]) }
        $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
        try { return ((& $exe @rest 2>&1) | Out-String) } catch { return "" } finally { $ErrorActionPreference = $old }
    }

    function Ver-Ge($a, $b) {
        try {
            $pa = (@($a.Split(".")) + @("0", "0", "0"))[0..2] -join "."
            $pb = (@($b.Split(".")) + @("0", "0", "0"))[0..2] -join "."
            return ([version]$pa -ge [version]$pb)
        } catch { return $true }
    }

    # CRC-32, the checksum Gephi records for installed plugin files.
    if (-not ("GephiAICrc32" -as [type])) {
        Add-Type -TypeDefinition @"
public static class GephiAICrc32 {
    static readonly uint[] T = Make();
    static uint[] Make() {
        var t = new uint[256];
        for (uint i = 0; i < 256; i++) { uint c = i; for (int k = 0; k < 8; k++) c = (c & 1) != 0 ? 0xEDB88320u ^ (c >> 1) : c >> 1; t[i] = c; }
        return t;
    }
    public static uint Of(byte[] b) {
        uint c = 0xFFFFFFFFu;
        foreach (byte x in b) c = T[(c ^ x) & 0xFF] ^ (c >> 8);
        return c ^ 0xFFFFFFFFu;
    }
}
"@
    }

    function Write-Utf8($path, $text) {
        # Without a byte-order mark: Windows PowerShell 5.1 adds one by default,
        # and some readers then refuse the file.
        [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false))
    }

    # ---------- release metadata ----------

    function Read-Release {
        Head "Looking up the $(if ($Version) { $Version } else { 'latest' }) release"
        $api = if ($Version) { "https://api.github.com/repos/$Repo/releases/tags/v$($Version.TrimStart('v'))" } else { "https://api.github.com/repos/$Repo/releases/latest" }
        $headers = @{ "User-Agent" = "gephi-ai-installer" }
        if ($env:GITHUB_TOKEN) { $headers["Authorization"] = "Bearer $env:GITHUB_TOKEN" }
        $rel = $null
        try { $rel = Invoke-RestMethod -Uri $api -Headers $headers } catch { }
        if (-not $rel) {
            # GitHub allows 60 API calls an hour per network address, which a classroom
            # on one network can use up. The release's latest.json is served from
            # elsewhere and carries the same versions, though not the checksums.
            $ref = if ($Version) { "v$($Version.TrimStart('v'))" } else { "main" }
            try { $m = Invoke-RestMethod -Uri "https://raw.githubusercontent.com/$Repo/$ref/latest.json" }
            catch {
                if ($Version) { throw "There is no Gephi AI release $Version. Releases: https://github.com/$Repo/releases" }
                throw "Could not reach GitHub. Check your internet connection and try again."
            }
            $r = @{ Server = $m.server; Nbm = $m.nbm; NbmSha = ""
                    NeedsGephi = $(if ($m.nbm_needs_gephi) { $m.nbm_needs_gephi } else { "0.11.3" }) }
            $r.NbmUrl = "https://github.com/$Repo/releases/download/v$($r.Server)/gephi-ai-$($r.Nbm).nbm"
            Warn "GitHub's API was unavailable (often its hourly limit on a shared network); using the release's version file"
            Ok "Gephi AI $($r.Server) (Gephi plugin $($r.Nbm), needs Gephi $($r.NeedsGephi) or newer)"
            return $r
        }
        $r = @{ Server = $rel.tag_name.TrimStart("v") }
        foreach ($a in $rel.assets) {
            $sha = if ($a.digest) { ($a.digest -replace "^sha256:", "") } else { "" }
            if ($a.name -like "*.nbm") { $r.NbmUrl = $a.browser_download_url; $r.NbmSha = $sha; $r.Nbm = ($a.name -replace "^gephi-ai-", "" -replace "\.nbm$", "") }
        }
        $r.NeedsGephi = "0.11.3"
        try {
            $latest = Invoke-RestMethod -Uri "https://raw.githubusercontent.com/$Repo/v$($r.Server)/latest.json"
            if ($latest.nbm_needs_gephi) { $r.NeedsGephi = $latest.nbm_needs_gephi }
        } catch { }
        Ok "Gephi AI $($r.Server) (Gephi plugin $($r.Nbm), needs Gephi $($r.NeedsGephi) or newer)"
        return $r
    }

    function Download($url, $sha, $dest) {
        Invoke-WebRequest -Uri $url -OutFile $dest -UseBasicParsing
        if ($sha) {
            $got = (Get-FileHash -Algorithm SHA256 $dest).Hash.ToLower()
            if ($got -ne $sha.ToLower()) { Remove-Item $dest -Force; throw "Checksum mismatch for $(Split-Path $url -Leaf). Expected $sha, got $got. Nothing was installed from it." }
            Ok "Downloaded $(Split-Path $url -Leaf) (checksum verified)"
        } else {
            Warn "Downloaded $(Split-Path $url -Leaf); GitHub published no checksum to verify it against"
        }
    }

    # ---------- Gephi Desktop ----------

    function Find-Gephi {
        $keys = "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*",
                "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
                "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\*"
        $found = @()
        foreach ($e in (Get-ItemProperty $keys -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -like "Gephi*" })) {
            $home_ = $e.InstallLocation
            if (-not $home_ -and $e.UninstallString) { $home_ = Split-Path ($e.UninstallString.Trim('"')) -Parent }
            if ($home_ -and (Test-Path (Join-Path $home_ "bin\gephi64.exe"))) {
                $v = if ($e.DisplayVersion) { $e.DisplayVersion } else { ($e.DisplayName -replace "[^0-9.]", "") }
                $found += [pscustomobject]@{ Home = $home_.TrimEnd("\"); Version = $v }
            }
        }
        foreach ($d in (Get-ChildItem "$env:ProgramFiles\Gephi*", "$env:LOCALAPPDATA\Programs\Gephi*" -Directory -ErrorAction SilentlyContinue)) {
            if ((Test-Path (Join-Path $d.FullName "bin\gephi64.exe")) -and -not ($found | Where-Object { $_.Home -eq $d.FullName })) {
                $found += [pscustomobject]@{ Home = $d.FullName; Version = ($d.Name -replace "^Gephi-", "") }
            }
        }
        if ($found.Count -eq 0) { return $null }
        # Newest first, when more than one is installed.
        return ($found | Sort-Object { try { [version]$_.Version } catch { [version]"0.0" } } -Descending | Select-Object -First 1)
    }

    function Find-Userdir($gephiHome) {
        $root = Join-Path $env:APPDATA "gephi"
        $line = $null
        $conf = Join-Path $gephiHome "etc\gephi.conf"
        if (Test-Path $conf) {
            $m = Select-String -Path $conf -Pattern '^default_userdir="(.*)"' | Select-Object -First 1
            if ($m) { $line = $m.Matches[0].Groups[1].Value }
        }
        if (-not $line) { $line = '${DEFAULT_USERDIR_ROOT}/0.11' }
        $line = $line.Replace('${DEFAULT_USERDIR_ROOT}', $root).Replace('${HOME}', $env:USERPROFILE).Replace('${APPDATA}', $env:APPDATA)
        $sep = [IO.Path]::DirectorySeparatorChar
        return [IO.Path]::GetFullPath($line.Replace("/", $sep).Replace("\", $sep))
    }

    # Newer Gephi releases ship the plugin themselves. The bundled module's file
    # names are not settled yet, so look for either name the plugin has had.
    # Returns the module's config file inside the Gephi installation, or $null.
    function Get-BundledModule($gephiHome) {
        if (-not $gephiHome) { return $null }
        return (Get-ChildItem -Path $gephiHome -Recurse -File -Include "*gephi-ai*.xml", "*gephi-mcp*.xml" -ErrorAction SilentlyContinue |
            Where-Object { $_.Directory.Name -eq "Modules" -and $_.Directory.Parent.Name -eq "config" } | Select-Object -First 1)
    }

    # The version Gephi recorded for a bundled module, read from its cluster's
    # update_tracking folder (config\Modules\x.xml -> update_tracking\x.xml).
    function Get-BundledVersion($module) {
        $t = Join-Path (Join-Path $module.Directory.Parent.Parent.FullName "update_tracking") $module.Name
        if (-not (Test-Path $t)) { return "" }
        $m = Select-String -Path $t -Pattern 'specification_version="([^"]*)"' | Select-Object -First 1
        if ($m) { return $m.Matches[0].Groups[1].Value } else { return "" }
    }

    function Get-GephiProcess { return Get-Process -Name gephi64, gephi -ErrorAction SilentlyContinue }

    function Get-Health {
        try { return Invoke-RestMethod -Uri "http://127.0.0.1:8080/health" -TimeoutSec 2 } catch { return $null }
    }

    function Close-Gephi {
        if (-not (Get-GephiProcess)) { return }
        Warn "Gephi is open. It has to be closed while the plugin is installed."
        $script:ClosedGephi = $true
        if (Ask "Close Gephi now? (it will ask to save anything unsaved)" "Y") {
            if ($DryRun) { Say "would close Gephi"; return }
            Get-GephiProcess | ForEach-Object { [void]$_.CloseMainWindow() }
        }
        if ($DryRun) { return }
        for ($i = 1; $i -le 60; $i++) {
            if (-not (Get-GephiProcess)) { Ok "Gephi is closed"; return }
            if ($i -eq 1) { Say "Waiting for Gephi to close..." }
            if ($i -eq 30) { Say "Still open. If Gephi is asking whether to save, answer it there." }
            Start-Sleep -Seconds 1
        }
        if (Ask "Gephi has not closed. Force it to quit? Anything unsaved in Gephi will be lost." "N") {
            Get-GephiProcess | Stop-Process -Force
            Start-Sleep -Seconds 3
            if (-not (Get-GephiProcess)) { Ok "Gephi is closed"; return }
        }
        throw "Gephi is still open. Close it and run this again."
    }

    function Remove-Tracked($userdir, $base) {
        $track = Join-Path $userdir "update_tracking\$base.xml"
        if (Test-Path $track) {
            foreach ($m in (Select-String -Path $track -Pattern 'name="([^"]*)"' -AllMatches).Matches) {
                $f = Join-Path $userdir ($m.Groups[1].Value.Replace("/", "\"))
                if (Test-Path $f -PathType Leaf) { Remove-Item $f -Force }
            }
        }
        foreach ($p in @("modules\$base.jar", "config\Modules\$base.xml", "update_tracking\$base.xml",
                        ("modules\ext\org.gephi.plugins." + $base.Replace("org-gephi-plugins-", "")))) {
            $full = Join-Path $userdir $p
            if (Test-Path $full) { Remove-Item $full -Recurse -Force }
        }
    }

    function Install-Nbm($rel, $gephi) {
        Head "Gephi AI plugin for Gephi"
        $userdir = Find-Userdir $gephi.Home
        Ok "Gephi user folder: $userdir"

        # Plugin 1.2.x and older was named "Gephi AI (MCP)". Left in place it grabs
        # port 8080 first and the assistant talks to the old version.
        if ((Test-Path (Join-Path $userdir "modules\$LegacyBase.jar")) -or (Test-Path (Join-Path $userdir "update_tracking\$LegacyBase.xml"))) {
            Warn "An old version of the plugin (Gephi AI (MCP)) is installed and would block the new one on port 8080"
            if (Ask "Remove the old plugin? (a backup is kept)" "Y") {
                Close-Gephi
                $bak = Join-Path $env:USERPROFILE (".gephi-ai-installer\backup-" + (Get-Date -Format "yyyyMMdd-HHmmss"))
                if ($DryRun) { Say "would move the old plugin's files to $bak"; Done "Old Gephi AI (MCP) plugin: would be removed (dry run)" } else {
                    New-Item -ItemType Directory -Path $bak -Force | Out-Null
                    # Keep each file's place under the user folder: config\Modules and update_tracking
                    # hold files with the same name.
                    $root = (Resolve-Path $userdir).Path.TrimEnd('\') + '\'
                    Get-ChildItem $userdir -Recurse -File | Where-Object { $_.FullName -like "*gephi-mcp*" } |
                        ForEach-Object {
                            $dest = Join-Path $bak $_.FullName.Substring($root.Length)
                            New-Item -ItemType Directory -Path (Split-Path $dest) -Force | Out-Null
                            Copy-Item $_.FullName -Destination $dest -Force
                        }
                    Remove-Tracked $userdir $LegacyBase
                    Ok "Removed the old plugin (backup in $bak)"
                    Done "Removed the old Gephi AI (MCP) plugin"
                }
            } else {
                Warn "Keeping it. Uninstall Gephi AI (MCP) in Tools > Plugins > Installed before using the new plugin."
                $script:Next.Add("In Gephi, Tools > Plugins > Installed: uninstall 'Gephi AI (MCP)', then restart Gephi.")
            }
        }

        $track = Join-Path $userdir "update_tracking\$ModuleBase.xml"
        $have = $null
        if (Test-Path $track) {
            $m = Select-String -Path $track -Pattern 'specification_version="([^"]*)"' | Select-Object -First 1
            if ($m) { $have = $m.Matches[0].Groups[1].Value }
        }
        $bundled = Get-BundledModule $gephi.Home
        if ($bundled) {
            $bver = Get-BundledVersion $bundled
            Ok ("Gephi $($gephi.Version) already includes the Gephi AI plugin" + $(if ($bver) { " ($bver)" } else { "" }))
            # A copy this installer added for an older Gephi would load instead of the
            # bundled one, or fight it for port 8080. Keep it only if it is newer.
            if ($have -and (-not $bver -or $have -eq $bver -or -not (Ver-Ge $have $bver))) {
                Say "Removing the separate copy ($have) added for an older Gephi, so Gephi uses its own"
                Close-Gephi
                if (-not $DryRun) {
                    Remove-Tracked $userdir $ModuleBase
                    $lm = Join-Path $userdir ".lastModified"
                    if (Test-Path $lm) { (Get-Item $lm -Force).LastWriteTime = Get-Date }
                }
            }
            Done ("Gephi plugin: built into Gephi" + $(if ($bver) { " ($bver)" } else { "" }))
            return $true
        }
        if ($have -eq $rel.Nbm -and (Test-Path (Join-Path $userdir "modules\$ModuleBase.jar"))) {
            Ok "Plugin $($rel.Nbm) is already installed"
            Done "Gephi plugin $($rel.Nbm) (already current)"
            return $true
        }
        if ($have) { Say "Updating the plugin from $have to $($rel.Nbm)" }

        Close-Gephi
        if ($DryRun) {
            Say "would download $($rel.NbmUrl) and unpack it into $userdir"
            Done "Gephi plugin $($rel.Nbm) (dry run)"
            return $true
        }
        $nbm = Join-Path $Tmp "gephi-ai.nbm"
        Download $rel.NbmUrl $rel.NbmSha $nbm
        $x = Join-Path $Tmp "nbm"
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        [IO.Compression.ZipFile]::ExtractToDirectory($nbm, $x)
        $nb = Join-Path $x "netbeans"
        if (-not (Test-Path (Join-Path $nb "modules\$ModuleBase.jar"))) { throw "The downloaded plugin file is not laid out as expected." }

        Remove-Tracked $userdir $ModuleBase
        New-Item -ItemType Directory -Path (Join-Path $userdir "update_tracking") -Force | Out-Null
        Copy-Item -Path (Join-Path $nb "*") -Destination $userdir -Recurse -Force

        # Tells Gephi its module list changed, so it rebuilds its cache at next start.
        $lm = Join-Path $userdir ".lastModified"
        if (Test-Path $lm) { (Get-Item $lm -Force).LastWriteTime = Get-Date } else { New-Item -ItemType File -Path $lm | Out-Null }

        # Record the install the way Gephi's own installer does, so Tools > Plugins
        # lists it and can uninstall or update it later. Written last: a re-run takes
        # this record to mean the install finished.
        $info = Get-Content (Join-Path $x "Info\info.xml") -Raw
        $codename = if ($info -match 'codenamebase="([^"]*)"') { $Matches[1] } else { "org.gephi.plugins.gephi.ai" }
        $now = [long]([DateTimeOffset]::UtcNow.ToUnixTimeMilliseconds())
        $lines = @('<?xml version="1.0" encoding="UTF-8" standalone="no"?>', "<module codename=`"$codename`">",
                   "    <module_version install_time=`"$now`" last=`"true`" origin=`"gephi-ai-$($rel.Nbm).nbm`" specification_version=`"$($rel.Nbm)`">")
        foreach ($f in (Get-ChildItem $nb -Recurse -File | Sort-Object FullName)) {
            $rel_ = $f.FullName.Substring($nb.Length + 1).Replace("\", "/")
            $crc = [GephiAICrc32]::Of([IO.File]::ReadAllBytes($f.FullName))
            $lines += "        <file crc=`"$crc`" name=`"$rel_`"/>"
        }
        $lines += "    </module_version>", "</module>"
        Write-Utf8 "$track.tmp" (($lines -join "`n") + "`n")
        Move-Item "$track.tmp" $track -Force

        Ok "Installed the Gephi plugin $($rel.Nbm)"
        Done "Gephi plugin $($rel.Nbm)"
        return $true
    }

    function Test-GephiConnection($rel, $gephi) {
        $h = Get-Health
        $opened = $false
        # Gephi opens only when asked to, or when the installer closed it.
        if (-not $h -and ($OpenGephi -or ($script:ClosedGephi -and -not $NoLaunch))) {
            Head "Checking that Gephi answers"
            if ($DryRun) { Say "would open Gephi and wait for the plugin on 127.0.0.1:8080"; return }
            $busy = Get-NetTCPConnection -LocalPort 8080 -State Listen -ErrorAction SilentlyContinue
            if ($busy -and -not (Get-GephiProcess)) {
                Warn "Another program is already using port 8080, so the plugin cannot start there."
                Say "In Gephi, Tools > Gephi AI Server lets you pick another port; set GEPHI_API_URL to match."
            }
            if (-not (Get-GephiProcess)) {
                if ($script:ClosedGephi) { Say "Reopening Gephi..." } else { Say "Opening Gephi (the first start can take a minute)..." }
                Start-Process -FilePath (Join-Path $gephi.Home "bin\gephi64.exe")
            }
            $opened = $true
            for ($i = 0; $i -lt 90 -and -not $h; $i++) { Start-Sleep -Seconds 2; $h = Get-Health }
        }
        if (-not $h) {
            if (-not $opened) { $script:Next.Add("Open Gephi. The plugin starts with it."); return }
            Warn "Gephi did not answer on port 8080 within 3 minutes."
            Say "Open Gephi and check Tools > Gephi AI Server. Its log is in $(Find-Userdir $gephi.Home)\var\log\messages.log"
            Fail "Gephi plugin did not answer; see Tools > Gephi AI Server"
            return
        }
        if (-not $opened) { Head "Checking that Gephi answers" }
        if ($h.version -ne $rel.Nbm -and -not (Get-BundledModule $gephi.Home)) {
            Warn "Gephi answered with plugin $($h.version), not $($rel.Nbm). Restart Gephi; if it persists, check Tools > Plugins > Installed for a second copy."
            Fail "Gephi answered with plugin $($h.version) instead of $($rel.Nbm)"
        } else {
            Ok "Gephi is running with the plugin ($($h.version))"
            Done "Gephi answers on 127.0.0.1:8080 (plugin $($h.version))"
        }
    }

    # ---------- uv ----------

    function Ensure-Uv {
        Head "uv (runs the Gephi AI server)"
        foreach ($c in @((Get-Command uvx -ErrorAction SilentlyContinue).Source, "$env:USERPROFILE\.local\bin\uvx.exe", "$env:USERPROFILE\.cargo\bin\uvx.exe")) {
            if ($c -and (Test-Path $c)) { $script:Uvx = $c; Ok "Found uvx at $c"; return }
        }
        Warn "uv is not installed. The assistants use it to run the Gephi AI server."
        if (-not (Ask "Install uv now (from astral.sh, the official installer)?" "Y")) { throw "uv is required. Install it from https://docs.astral.sh/uv/ and run this again." }
        $script:Uvx = "$env:USERPROFILE\.local\bin\uvx.exe"
        if ($DryRun) { Say "would run: irm https://astral.sh/uv/install.ps1 | iex"; return }
        Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
        if (-not (Test-Path $script:Uvx)) { throw "uv installed, but uvx was not found at $script:Uvx." }
        $env:Path = (Split-Path $script:Uvx) + ";" + $env:Path
        Ok "Installed uv"
        Done "Installed uv"
        $script:Next.Add("Open a new PowerShell or terminal window so 'uvx' is on your PATH before starting your assistant.")
    }

    # Start the server once and send it the MCP handshake. This proves it runs, and
    # downloads it and its Python now; otherwise the first launch does that inside
    # the assistant and can run past the assistant's startup timeout.
    function Test-Server($spec) {
        if ($DryRun) { Say "would start $spec once and check that it answers"; return }
        $req = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"installer","version":"1.0"}}}'
        $psi = New-Object Diagnostics.ProcessStartInfo
        $psi.FileName = $script:Uvx
        $psi.Arguments = "--quiet --from `"$spec`" gephi-ai"
        $psi.RedirectStandardInput = $true; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
        $psi.UseShellExecute = $false
        $p = [Diagnostics.Process]::Start($psi)
        $p.StandardInput.WriteLine($req); $p.StandardInput.Close()
        $errTask = $p.StandardError.ReadToEndAsync()
        $outTask = $p.StandardOutput.ReadToEndAsync()
        if (-not $p.WaitForExit(300000)) { $p.Kill() }
        if ($outTask.Result -match '"serverInfo"') {
            Ok "The Gephi AI server ($spec) starts and answers"
        } else {
            Warn "The Gephi AI server ($spec) did not answer. Its last messages:"
            ($errTask.Result -split "`n" | Select-Object -Last 5) | ForEach-Object { Say "    $_" }
            Fail "Gephi AI server did not start; see the log"
        }
    }

    # ---------- assistants ----------

    function Setup-ClaudeCode {
        Head "Claude Code"
        if ((Output-Of claude plugin marketplace list) -match "(^|\s)$Marketplace\s*(\r?\n|$)") { [void](Run claude plugin marketplace update $Marketplace) }
        else { if (-not (Run claude plugin marketplace add $Repo)) { throw "claude plugin marketplace add failed" } }
        if ((Output-Of claude plugin list) -match [regex]::Escape($Plugin)) { [void](Run claude plugin update $Plugin) }
        else { if (-not (Run claude plugin install $Plugin)) { throw "claude plugin install failed" } }
        # The plugin brings its own server. A hand-registered one beside it means
        # two servers and every tool listed twice. `claude mcp get` exits 0 even
        # when it finds nothing, so read what it says.
        foreach ($n in "gephi-ai", "gephi-mcp") {
            $o = Output-Of claude mcp get $n
            if ($o -and $o -notmatch "No MCP server found") {
                Warn "A separately registered '$n' server would duplicate the plugin's tools"
                if (Ask "Remove the separate '$n' registration?" "Y") { [void](Run claude mcp remove -s user $n) }
            }
        }
        Ok "Claude Code has the Gephi AI plugin"
        Done "Claude Code: plugin $Plugin"
        $script:Next.Add("Claude Code: start a new session to load the plugin.")
    }

    function Setup-Codex {
        Head "OpenAI Codex"
        if ((Output-Of codex plugin marketplace list) -match "(?m)^$Marketplace\s") { [void](Run codex plugin marketplace upgrade $Marketplace) }
        else { if (-not (Run codex plugin marketplace add $Repo --ref main)) { throw "codex plugin marketplace add failed" } }
        if (-not (Run codex plugin add $Plugin)) { throw "codex plugin add failed" }
        $cfg = Join-Path $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { "$env:USERPROFILE\.codex" }) "config.toml"
        foreach ($n in "gephi-ai", "gephi-mcp") {
            if ((Test-Path $cfg) -and (Select-String -Path $cfg -Pattern "^\[mcp_servers\.$n\]" -Quiet)) {
                Warn "A separately registered '$n' server would duplicate the plugin's tools"
                if (Ask "Remove the separate '$n' registration?" "Y") { [void](Run codex mcp remove $n) }
            }
        }
        Ok "Codex has the Gephi AI plugin"
        Done "Codex: plugin $Plugin"
        $script:Next.Add("Codex: start a new task to load the plugin.")
    }

    function Setup-Gemini {
        Head "Gemini CLI"
        $list = Output-Of gemini mcp list
        if ($list -match "gephi-mcp") {
            Warn "Found the old 'gephi-mcp' registration; replacing it with 'gephi-ai'"
            [void](Run gemini mcp remove -s user gephi-mcp)
        }
        if ($list -match "gephi-ai") { Ok "Gemini CLI already has gephi-ai" }
        else {
            if (-not (Run gemini mcp add -s user gephi-ai $script:Uvx gephi-ai)) { throw "gemini mcp add failed" }
            Ok "Registered gephi-ai with Gemini CLI"
        }
        Test-Server "gephi-ai"
        Done "Gemini CLI: gephi-ai server"
    }

    function Desktop-Config { return (Join-Path $env:APPDATA "Claude\claude_desktop_config.json") }
    function Desktop-Ext { return (Join-Path $env:APPDATA "Claude\Claude Extensions\local.mcpb.matt-artz.gephi-ai") }

    function Uv-Exe {
        $dir = Split-Path $script:Uvx
        foreach ($n in "uv.exe", "uv") { $p = Join-Path $dir $n; if (Test-Path $p) { return $p } }
        return "uv"
    }

    # Claude Desktop reads its servers from a JSON file, which needs no click to
    # change (installing an extension does). Desktop apps do not see the
    # terminal's PATH, so the entry names uvx by its full path. The edit runs in
    # Python through uv, the same code install.sh uses, and keeps a backup.
    $DesktopEditPy = @'
import json, os, shutil, sys, time
action, path, uvx, spec = sys.argv[1:5]
# Write through a symlinked settings file, not over the link.
path = os.path.realpath(path)
try:
    with open(path, encoding="utf-8-sig") as f:
        text = f.read()
    cfg = json.loads(text) if text.strip() else {}
except FileNotFoundError:
    cfg = {}
except json.JSONDecodeError as e:
    print(f"invalid:{e}")
    sys.exit(0)
servers = cfg.setdefault("mcpServers", {})
old = servers.get("gephi-ai")
if action == "remove":
    if old is None:
        print("absent")
        sys.exit(0)
    # Remove only the entry this installer writes (one that runs uvx).
    cmd = os.path.basename(str(old.get("command", ""))).lower()
    if cmd not in ("uvx", "uvx.exe"):
        print("custom:" + str(old.get("command", "")))
        sys.exit(0)
    del servers["gephi-ai"]
    result = "removed"
else:
    # The server's old name runs the same tools; adding gephi-ai beside it
    # would list every tool twice.
    if "gephi-mcp" in servers and action != "replace":
        print("legacy")
        sys.exit(0)
    # An entry that does not run uvx is someone's own setup (a development
    # checkout, a custom launcher). Replace it only when asked to.
    cmd = os.path.basename(str((old or {}).get("command", ""))).lower()
    if old and cmd not in ("uvx", "uvx.exe") and action != "replace":
        print("custom:" + str(old.get("command", "")))
        sys.exit(0)
    servers.pop("gephi-mcp", None)
    # Keep anything else the user put in the entry, such as an env block.
    entry = {**(old or {}), "command": uvx, "args": ["--from", spec, "gephi-ai"]}
    if entry == old:
        print("current")
        sys.exit(0)
    servers["gephi-ai"] = entry
    result = "updated" if old else "added"
if os.path.exists(path):
    shutil.copy2(path, path + time.strftime(".bak-%Y%m%d-%H%M%S"))
tmp = path + ".tmp"
with open(tmp, "w", encoding="utf-8") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
os.replace(tmp, path)
print(result)
'@

    function Edit-Desktop($action, $spec) {
        $cfg = Desktop-Config
        New-Item -ItemType Directory -Path (Split-Path $cfg) -Force | Out-Null
        $py = Join-Path ([IO.Path]::GetTempPath()) ("gephi-ai-desktop-" + [guid]::NewGuid().ToString("N").Substring(0, 8) + ".py")
        [IO.File]::WriteAllText($py, $DesktopEditPy, (New-Object Text.UTF8Encoding $false))
        try {
            $old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
            # PowerShell drops a $null argument outright, which would shift the rest;
            # an uninstall has no version to pass.
            if (-not $spec) { $spec = "-" }
            $out = (& (Uv-Exe) run --no-project --quiet python $py $action $cfg $script:Uvx $spec 2>&1 | Out-String).Trim()
            $ErrorActionPreference = $old
            return ($out -split "`r?`n" | Select-Object -Last 1)
        } finally { Remove-Item $py -Force -ErrorAction SilentlyContinue }
    }

    function Setup-Desktop($rel) {
        Head "Claude Desktop"
        # Someone who installed the Gephi AI extension keeps it; a config entry
        # beside it would list every tool twice.
        $ext = Join-Path (Desktop-Ext) "manifest.json"
        if (Test-Path $ext) {
            $have = $null
            try { $have = (Get-Content $ext -Raw | ConvertFrom-Json).version } catch { }
            if ($have -eq $rel.Server) {
                Ok "The Gephi AI extension $have is already installed"
                Done "Claude Desktop: extension $have (already current)"
            } else {
                Ok "Claude Desktop has the Gephi AI extension $have"
                Done "Claude Desktop: extension $have (update it in Settings > Extensions)"
                $script:Next.Add("Claude Desktop: Settings > Extensions > Gephi AI > Update, to move to $($rel.Server).")
            }
            return
        }
        $spec = "gephi-ai==$($rel.Server)"
        if ($DryRun) { Say "would add or update `"gephi-ai`" in $(Desktop-Config) (backup kept)"; Done "Claude Desktop: gephi-ai $($rel.Server) (dry run)"; return }
        $result = Edit-Desktop "add" $spec
        if ($result -like "custom:*" -or $result -eq "legacy") {
            if ($result -eq "legacy") { Warn "Claude Desktop runs Gephi AI under its old name, gephi-mcp" }
            else { Warn "Claude Desktop already runs Gephi AI through your own command: $($result.Substring(7))" }
            if (Ask "Replace it with the standard setup? (a backup is kept)" "N") { $result = Edit-Desktop "replace" $spec }
            else {
                Ok "Kept your own Claude Desktop setup"
                Skip "Claude Desktop: kept your own setup"
                return
            }
        }
        switch -Wildcard ($result) {
            "current" { Ok "Claude Desktop already has gephi-ai $($rel.Server)"; Done "Claude Desktop: gephi-ai $($rel.Server) (already current)" }
            { $_ -eq "added" -or $_ -eq "updated" } {
                Ok "Added gephi-ai $($rel.Server) to Claude Desktop's settings (backup kept beside them)"
                Done "Claude Desktop: gephi-ai $($rel.Server)"
                $script:Next.Add("Claude Desktop: quit it fully (File > Exit, or from the tray icon) and reopen it to load Gephi AI.")
            }
            "invalid:*" { Warn "Claude Desktop's config file is not valid JSON, so it was left alone: $($result.Substring(8))"; Fail "Claude Desktop: config file is not valid JSON; fix $(Desktop-Config) and re-run" }
            default { Fail "Claude Desktop: could not update $(Desktop-Config) ($result)" }
        }
    }

    # ---------- uninstall ----------

    function Remove-GephiAI {
        Head "Removing Gephi AI"
        if (Has claude) {
            if ((Output-Of claude plugin list) -match [regex]::Escape($Plugin)) { [void](Run claude plugin uninstall $Plugin) }
            if ((Output-Of claude plugin marketplace list) -match "(^|\s)$Marketplace\s*(\r?\n|$)") { [void](Run claude plugin marketplace remove $Marketplace) }
        }
        if ((Has codex) -and ((Output-Of codex plugin marketplace list) -match "(?m)^$Marketplace\s")) {
            [void](Run codex plugin remove $Plugin)
            [void](Run codex plugin marketplace remove $Marketplace)
        }
        if ((Has gemini) -and ((Output-Of gemini mcp list) -match "gephi-ai")) { [void](Run gemini mcp remove -s user gephi-ai) }
        $g = Find-Gephi
        if ($g) {
            $userdir = Find-Userdir $g.Home
            if (Test-Path (Join-Path $userdir "modules\$ModuleBase.jar")) {
                Close-Gephi
                if (-not $DryRun) { Remove-Tracked $userdir $ModuleBase }
                Ok "Removed the Gephi plugin from $userdir"
            }
        }
        $dc = Desktop-Config
        if ((Test-Path $dc) -and (Select-String -Path $dc -Pattern '"gephi-ai"' -Quiet)) {
            if ($DryRun) { Say "would remove `"gephi-ai`" from $dc" }
            else {
                $script:Uvx = (Get-Command uvx -ErrorAction SilentlyContinue).Source
                if (-not $script:Uvx) { Warn "uv is not installed, so `"gephi-ai`" was left in $dc; remove it by hand" }
                else {
                    $result = Edit-Desktop "remove" $null
                    if ($result -eq "removed") { Ok "Removed gephi-ai from Claude Desktop's settings (backup kept)" }
                    elseif ($result -like "custom:*") { Warn "Left Claude Desktop's `"gephi-ai`" entry alone: it runs your own command ($($result.Substring(7)))" }
                }
            }
        }
        if (Test-Path (Desktop-Ext)) {
            Say "Claude Desktop: remove the extension in Settings > Extensions."
        }
        Ok "Done. uv and Gephi Desktop were left installed."
    }

    # ---------- main ----------

    try { Start-Transcript -Path $Log -Append | Out-Null } catch { }
    try {
        # Assistants read project settings from the current folder; work from home
        # so a folder the user happens to be in cannot change what is detected.
        Push-Location $env:USERPROFILE
        Write-Host ("Gephi AI installer" + $(if ($DryRun) { " (dry run: nothing will change)" } else { "" })) -ForegroundColor White

        if ($Uninstall) { Remove-GephiAI; return }

        if (-not $Clients) {
            $found = @()
            if (Has claude) { $found += "claude" }
            if (Has codex) { $found += "codex" }
            if (Has gemini) { $found += "gemini" }
            if (($env:APPDATA -and (Test-Path (Join-Path $env:APPDATA "Claude"))) -or ($env:LOCALAPPDATA -and (Test-Path (Join-Path $env:LOCALAPPDATA "AnthropicClaude")))) { $found += "desktop" }
            $Clients = $found -join ","
        }
        # -Clients codex,gemini arrives as an array, "codex,gemini" as one string.
        $want = @(($Clients -join ",").Split(",") | ForEach-Object { $_.Trim().ToLower() } | Where-Object { $_ })
        foreach ($c in $want) {
            if ($c -notin "claude", "codex", "gemini", "desktop") { throw "Unknown assistant '$c'. Choose from: claude, codex, gemini, desktop" }
        }

        $rel = Read-Release

        Head "Plan"
        if ($SkipGephiPlugin) { Say "- Gephi Desktop: leave alone" }
        elseif ((Find-Gephi) -and (Get-BundledModule (Find-Gephi).Home)) { Say "- Gephi Desktop: already includes the Gephi AI plugin" }
        else { Say "- Gephi Desktop: install or update the Gephi AI plugin $($rel.Nbm)" }
        if ($want -contains "claude") { Say "- Claude Code: install or update the gephi-network-analysis plugin" }
        if ($want -contains "codex") { Say "- OpenAI Codex: install or update the gephi-network-analysis plugin" }
        if ($want -contains "gemini") { Say "- Gemini CLI: register the gephi-ai server" }
        if ($want -contains "desktop") { Say "- Claude Desktop: add Gephi AI $($rel.Server) to its settings" }
        if ($want.Count -eq 0) {
            Warn "No AI assistant found (looked for Claude Code, Codex, Gemini CLI, Claude Desktop)."
            Say "  Install one, then re-run. Any other MCP client can run 'uvx gephi-ai' over stdio."
        }
        if (-not (Ask "Go ahead?" "Y")) { Write-Host "Nothing changed."; return }

        $gephi = $null; $nbmOk = $false
        if (-not $SkipGephiPlugin) {
            Head "Gephi Desktop"
            $gephi = Find-Gephi
            if (-not $gephi) {
                Warn "Gephi Desktop is not installed"
                Say "Download Gephi from $DownloadPage, install it, open it once, then run this again."
                Say "The assistant setup below still goes ahead, so the re-run will only add the Gephi plugin."
                if (-not $DryRun) { try { Start-Process $DownloadPage } catch { } }
                Skip "Gephi plugin not installed: Gephi Desktop is missing"
                $script:Next.Add("Install Gephi from $DownloadPage, then re-run this installer to add the plugin.")
            } elseif ($gephi.Version -and -not (Ver-Ge $gephi.Version $rel.NeedsGephi)) {
                Warn "Gephi $($gephi.Version) is installed; the plugin needs $($rel.NeedsGephi) or newer"
                Say "Download the newest Gephi from $DownloadPage, install it, and run this again."
                Fail "Gephi $($gephi.Version) is too old for the plugin (needs $($rel.NeedsGephi))"
                $script:Next.Add("Update Gephi from $DownloadPage, then re-run this installer.")
                $gephi = $null
            } else {
                Ok "Found Gephi $($gephi.Version) at $($gephi.Home)"
                $nbmOk = Install-Nbm $rel $gephi
            }
        }

        if ($want -contains "claude" -or $want -contains "codex" -or $want -contains "gemini" -or $want -contains "desktop") { Ensure-Uv }
        if ($want -contains "claude" -or $want -contains "codex" -or $want -contains "desktop") {
            Head "Checking the Gephi AI server"
            Test-Server "gephi-ai==$($rel.Server)"
        }

        # One assistant failing should not stop the others.
        foreach ($c in "claude", "codex", "gemini", "desktop") {
            if ($want -notcontains $c) { continue }
            try {
                switch ($c) {
                    "claude" { if (Has claude) { Setup-ClaudeCode } else { Skip "Claude Code: not installed" } }
                    "codex" { if (Has codex) { Setup-Codex } else { Skip "Codex: not installed" } }
                    "gemini" { if (Has gemini) { Setup-Gemini } else { Skip "Gemini CLI: not installed" } }
                    "desktop" { Setup-Desktop $rel }
                }
            } catch {
                Warn $_.Exception.Message
                Fail "${c}: setup failed (details above)"
            }
        }

        if ($nbmOk -and $gephi) { Test-GephiConnection $rel $gephi }

        Head "Summary"
        foreach ($l in $script:Summary) {
            $color = if ($l.StartsWith("[ok]")) { "Green" } elseif ($l.StartsWith("[fail]")) { "Red" } else { "Yellow" }
            Write-Host "  $l" -ForegroundColor $color
        }
        if ($script:Next.Count -gt 0) {
            Write-Host ""; Write-Host "Next steps" -ForegroundColor White
            foreach ($l in $script:Next) { Write-Host "  - $l" }
        }
        Write-Host ""
        Write-Host "Then, with Gephi open, ask your assistant: `"Check if Gephi is running.`""
        Write-Host "Log: $Log" -ForegroundColor DarkGray
    } catch {
        Write-Host ""
        Write-Host "x Stopped while: $script:Step" -ForegroundColor Red
        Write-Host "  $($_.Exception.Message)" -ForegroundColor Red
        Write-Host "  Re-run the same command to retry; finished steps are skipped."
        Write-Host "  Full log: $Log"
        Write-Host "  Attach it to an issue at https://github.com/$Repo/issues"
        $script:Failed = $true
    } finally {
        Pop-Location -ErrorAction SilentlyContinue
        Remove-Item $Tmp -Recurse -Force -ErrorAction SilentlyContinue
        try { Stop-Transcript | Out-Null } catch { }
    }
}

$script:Failed = $false
Install-GephiAI -Yes:$Yes -DryRun:$DryRun -Clients $Clients -SkipGephiPlugin:$SkipGephiPlugin -Version $Version -NoLaunch:$NoLaunch -OpenGephi:$OpenGephi -Uninstall:$Uninstall
# Run as a file, a failed step gives a non-zero exit for scripts and CI. Under
# `irm | iex` there is no file, and exiting would close the user's window.
if ($script:Failed -and $MyInvocation.MyCommand.Path) { exit 1 }
