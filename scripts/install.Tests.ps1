# Pester tests for install.ps1. The script is dot-sourced with GEPHI_AI_INSTALLER_TEST=1, which
# skips the final Install-GephiAI call. Its helpers are nested inside Install-GephiAI, so each is
# pulled out of the parsed script and defined globally here (a definition dot-sourced inside a
# helper function would vanish when the helper returns). Nothing touches the network.
# Run: Invoke-Pester scripts/install.Tests.ps1

BeforeAll {
    $env:GEPHI_AI_INSTALLER_TEST = "1"
    $script:Installer = Join-Path $PSScriptRoot "..\install.ps1"
    . $script:Installer
    $ast = (Get-Command Install-GephiAI).ScriptBlock.Ast
    function Import-Nested($name, $rename = @{}) {
        $def = $ast.Find({ param($n) $n -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name }, $true)
        if (-not $def) { throw "install.ps1 has no function $name" }
        $text = $def.Extent.Text
        foreach ($k in $rename.Keys) { $text = $text.Replace($k, $rename[$k]) }
        # Define it globally: dot-sourced here, it would live only in this helper's scope.
        $text = $text -replace "^function\s+$name\b", "function global:$name"
        . ([scriptblock]::Create($text))
    }
    Import-Nested "Ver-Core"
    Import-Nested "Ver-Ge"
    Import-Nested "Get-Health"
    # Download reads the installer's $AllowUnverified; the tests set a global in its place.
    Import-Nested "Download" @{ '$AllowUnverified' = '$global:TestAllowUnverified' }
    function global:Ok($t) { }
    function global:Warn($t) { }
}

AfterAll {
    foreach ($f in 'Ver-Core', 'Ver-Ge', 'Get-Health', 'Download', 'Ok', 'Warn') {
        Remove-Item "Function:\global:$f" -ErrorAction SilentlyContinue
    }
    Remove-Item Env:GEPHI_AI_INSTALLER_TEST -ErrorAction SilentlyContinue
    Remove-Variable TestAllowUnverified, TestSrc, TestDest -Scope Global -ErrorAction SilentlyContinue
}

Describe "Ver-Ge" {
    It "compares <a> >= <b> as <want>" -ForEach @(
        @{ a = "0.11.4";    b = "0.11.4"; want = $true }
        @{ a = "0.11.5";    b = "0.11.4"; want = $true }
        @{ a = "0.11.10";   b = "0.11.4"; want = $true }
        @{ a = "0.11.3";    b = "0.11.4"; want = $false }
        @{ a = "0.11.3-rc"; b = "0.11.4"; want = $false }
        @{ a = "0.11.4-rc"; b = "0.11.4"; want = $true }
        @{ a = "abc";       b = "0.11.4"; want = $false }
        @{ a = "";          b = "0.11.4"; want = $false }
    ) {
        Ver-Ge $a $b | Should -Be $want
    }
}

Describe "Download" {
    BeforeEach {
        $global:TestAllowUnverified = $false
        $global:TestDest = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
        $global:TestSrc = Join-Path ([IO.Path]::GetTempPath()) ([guid]::NewGuid().ToString())
        Set-Content -Path $global:TestSrc -Value "payload" -NoNewline
        Mock Invoke-WebRequest { Copy-Item $global:TestSrc $OutFile } -Verifiable
    }
    AfterEach { Remove-Item $global:TestDest, $global:TestSrc -ErrorAction SilentlyContinue }

    It "refuses with no checksum and fetches nothing" {
        { Download "https://example.invalid/a.nbm" "" $global:TestDest } | Should -Throw "*No checksum is available*"
        Should -Invoke Invoke-WebRequest -Times 0
    }
    It "refuses a checksum mismatch and removes the file" {
        { Download "https://example.invalid/a.nbm" ("0" * 64) $global:TestDest } | Should -Throw "*Checksum mismatch*"
        Test-Path $global:TestDest | Should -BeFalse
    }
    It "accepts the right checksum" {
        $sha = (Get-FileHash -Algorithm SHA256 $global:TestSrc).Hash
        { Download "https://example.invalid/a.nbm" $sha $global:TestDest } | Should -Not -Throw
        Test-Path $global:TestDest | Should -BeTrue
    }
    It "allows no checksum when AllowUnverified is set" {
        $global:TestAllowUnverified = $true
        { Download "https://example.invalid/a.nbm" "" $global:TestDest } | Should -Not -Throw
    }
}

Describe "Get-Health" {
    It "asks the quick health answer and waits 5 seconds" {
        Mock Invoke-RestMethod { @{ status = "running" } } -Verifiable
        (Get-Health).status | Should -Be "running"
        Should -Invoke Invoke-RestMethod -Times 1 -ParameterFilter {
            $Uri -eq "http://127.0.0.1:8080/health?quick=true" -and $TimeoutSec -eq 5
        }
    }
    It "reads a Gephi that does not answer as not running" {
        Mock Invoke-RestMethod { throw "timed out" }
        Get-Health | Should -BeNullOrEmpty
    }
}
