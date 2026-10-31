param(
    [string]$RepoRoot = (Join-Path $PSScriptRoot "..")
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path
$Failures = [System.Collections.Generic.List[string]]::new()
$JsonCache = @{}

function Add-Failure([string]$Message) {
    $Failures.Add($Message)
}

function Read-Json([string]$RelativePath) {
    $Path = Join-Path $RepoRoot $RelativePath
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        Add-Failure "$RelativePath`: missing"
        $JsonCache[$RelativePath] = $null
        return $null
    }
    try {
        $Value = Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json
        $JsonCache[$RelativePath] = $Value
        return $Value
    } catch {
        Add-Failure "$RelativePath`: invalid JSON"
        $JsonCache[$RelativePath] = $null
        return $null
    }
}

function Get-Json([string]$RelativePath) {
    if (-not $JsonCache.ContainsKey($RelativePath)) {
        return Read-Json $RelativePath
    }
    return $JsonCache[$RelativePath]
}

function Get-PluginSource($Entry) {
    if ($Entry.source -is [string]) { return $Entry.source }
    return [string]$Entry.source.path
}

function Check-Marketplace([string]$RelativePath, [string[]]$PluginNames) {
    $Market = Get-Json $RelativePath
    if ($null -eq $Market) { return }
    foreach ($Entry in @($Market.plugins)) {
        $Name = [string]$Entry.name
        $Source = Get-PluginSource $Entry
        if (-not $Source.StartsWith("./")) {
            Add-Failure "$RelativePath`: source '$Source' for '$Name' must start with ./"
            continue
        }
        if ($Source.Split("/") -contains "..") {
            Add-Failure "$RelativePath`: source '$Source' for '$Name' contains .."
            continue
        }
        $SourcePath = Join-Path $RepoRoot $Source.Substring(2)
        if (-not (Test-Path -LiteralPath $SourcePath -PathType Container)) {
            Add-Failure "$RelativePath`: source path '$Source' for '$Name' does not exist"
        }
        if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot "plugins/$Name") -PathType Container)) {
            Add-Failure "$RelativePath`: plugin '$Name' has no plugins/$Name directory"
        }
    }
    foreach ($Name in $PluginNames) {
        if (@($Market.plugins | ForEach-Object { [string]$_.name }) -notcontains $Name) {
            Add-Failure "$RelativePath`: plugin '$Name' not listed"
        }
    }
}

$ClaudeMarketplace = Read-Json ".claude-plugin/marketplace.json"
$AgentsMarketplace = Read-Json ".agents/plugins/marketplace.json"
$MuseMarketplacePath = Join-Path $RepoRoot ".muse-plugin/marketplace.json"
if (Test-Path -LiteralPath $MuseMarketplacePath -PathType Leaf) {
    [void](Read-Json ".muse-plugin/marketplace.json")
}

$PluginDirs = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot "plugins") -Directory -ErrorAction SilentlyContinue)
$PluginNames = @($PluginDirs | ForEach-Object { $_.Name })
$ManifestPaths = @(".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".muse-plugin/plugin.json")

if ($PluginNames.Count -eq 0) { Add-Failure "no plugins found at plugins/*" }
foreach ($Plugin in $PluginDirs) {
    $ReferenceVersion = $null
    $ReferencePath = $null
    foreach ($Manifest in $ManifestPaths) {
        $RelativePath = "plugins/$($Plugin.Name)/$Manifest"
        $Data = Read-Json $RelativePath
        if ($null -eq $Data) { continue }
        if (-not $Data.name) { Add-Failure "$RelativePath`: missing name" }
        if (-not $Data.version) { Add-Failure "$RelativePath`: missing version" }
        if ($Data.name -ne $Plugin.Name) {
            Add-Failure "$RelativePath`: name '$($Data.name)' != directory '$($Plugin.Name)'"
        }
        if ($null -eq $ReferencePath) {
            $ReferencePath = $RelativePath
            $ReferenceVersion = $Data.version
        } elseif ($Data.version -ne $ReferenceVersion) {
            Add-Failure "$RelativePath`: version '$($Data.version)' != '$ReferenceVersion' in $ReferencePath"
        }
    }
}

if ($null -ne $ClaudeMarketplace -and -not $ClaudeMarketplace.name) {
    Add-Failure ".claude-plugin/marketplace.json`: missing name"
}
Check-Marketplace ".claude-plugin/marketplace.json" $PluginNames
Check-Marketplace ".agents/plugins/marketplace.json" $PluginNames
if (Test-Path -LiteralPath $MuseMarketplacePath -PathType Leaf) {
    Check-Marketplace ".muse-plugin/marketplace.json" $PluginNames
}

$Skills = @(Get-ChildItem -LiteralPath (Join-Path $RepoRoot "plugins") -Filter "SKILL.md" -File -Recurse)
$SkillNames = [System.Collections.Generic.List[string]]::new()
foreach ($SkillFile in $Skills) {
    $SkillDir = $SkillFile.Directory.Name
    $SkillNames.Add($SkillDir)
    $Lines = (Get-Content -LiteralPath $SkillFile.FullName -Raw -Encoding UTF8) -split "`r?`n"
    if ($Lines.Count -eq 0 -or $Lines[0].TrimStart([char]0xFEFF) -ne "---") {
        Add-Failure "$($SkillFile.FullName): missing or malformed frontmatter"
        continue
    }
    $End = [Array]::IndexOf($Lines, "---", 1)
    if ($End -lt 0) {
        Add-Failure "$($SkillFile.FullName): missing or malformed frontmatter"
        continue
    }
    $Frontmatter = if ($End -gt 1) { @($Lines[1..($End - 1)]) } else { @() }
    $NameMatch = $Frontmatter | Where-Object { $_ -match '^name:[ \t]*(.*?)[ \t]*$' } | Select-Object -First 1
    $DescriptionIndex = -1
    $DescriptionValue = ""
    for ($Index = 0; $Index -lt $Frontmatter.Count; $Index++) {
        if ($Frontmatter[$Index] -match '^description:[ \t]*(.*?)[ \t]*$') {
            $DescriptionIndex = $Index
            $DescriptionValue = $Matches[1].Trim("'", '"')
            break
        }
    }
    $Name = if ($NameMatch) { ($NameMatch -replace '^name:[ \t]*', '').Trim().Trim("'", '"') } else { "" }
    if (-not $NameMatch) {
        Add-Failure "$($SkillFile.FullName): missing or malformed frontmatter"
        continue
    }
    if ($Name -ne $SkillDir) { Add-Failure "$($SkillFile.FullName): frontmatter name '$Name' != folder '$SkillDir'" }

    $HasDescription = [bool]$DescriptionValue
    if (-not $HasDescription -and $DescriptionValue -match '^[>|][-+]?[0-9]*$') {
        for ($Index = $DescriptionIndex + 1; $Index -lt $Frontmatter.Count; $Index++) {
            if ($Frontmatter[$Index] -match '^\s+\S') { $HasDescription = $true; break }
        }
    }
    if (-not $HasDescription) { Add-Failure "$($SkillFile.FullName): description missing or empty" }
}

if ($Skills.Count -eq 0) { Add-Failure "no skills found at plugins/*/skills/*/SKILL.md" }
$DuplicateNames = @($SkillNames | Group-Object | Where-Object Count -gt 1 | ForEach-Object Name)
foreach ($Name in $DuplicateNames) { Add-Failure "skill '$Name' exists in more than one plugin" }
foreach ($SkillDir in Get-ChildItem -LiteralPath (Join-Path $RepoRoot "plugins") -Directory -Recurse | Where-Object { $_.Parent.Name -eq "skills" }) {
    if (-not (Test-Path -LiteralPath (Join-Path $SkillDir.FullName "SKILL.md") -PathType Leaf)) {
        Add-Failure "$($SkillDir.FullName)/SKILL.md: missing"
    }
}

$ShellFiles = Get-ChildItem -LiteralPath $RepoRoot -Filter "*.sh" -File -Recurse |
    Where-Object { $_.FullName -notmatch '[\\/](\.git|node_modules)[\\/]' }
foreach ($ShellFile in $ShellFiles) {
    if ([Array]::IndexOf([IO.File]::ReadAllBytes($ShellFile.FullName), [byte]13) -ge 0) {
        Add-Failure "$($ShellFile.FullName): contains CRLF line endings"
    }
}

if ($Failures.Count -gt 0) {
    foreach ($Failure in $Failures) { Write-Output "FAIL: $Failure" }
    Write-Output "validate.ps1: $($Failures.Count) failure(s)"
    exit 1
}

Write-Output "validate.ps1: OK ($($Skills.Count) skills, $($PluginNames.Count) plugins)"
exit 0
