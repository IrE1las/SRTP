param(
    [Parameter(Mandatory = $true)]
    [string]$SourcePath
)

# Re-export a teacher-approved workbook without editing it.  All deliberate
# outputs remain beside this script inside G:\gg\SRTP.
$resolvedSource = (Resolve-Path -LiteralPath $SourcePath -ErrorAction Stop).Path
$outputPath = Join-Path $PSScriptRoot 'source_data.json'
$excel = New-Object -ComObject Excel.Application
$excel.Visible = $false
$excel.DisplayAlerts = $false
$workbook = $null
try {
    $workbook = $excel.Workbooks.Open($resolvedSource, 0, $true)
    $sheets = [ordered]@{}
    foreach ($sheet in $workbook.Worksheets) {
        $cells = $sheet.UsedRange.Value2
        $rows = @()
        for ($rowIndex = $cells.GetLowerBound(0); $rowIndex -le $cells.GetUpperBound(0); $rowIndex++) {
            $row = @()
            for ($columnIndex = $cells.GetLowerBound(1); $columnIndex -le $cells.GetUpperBound(1); $columnIndex++) {
                $row += $cells[$rowIndex, $columnIndex]
            }
            $rows += ,$row
        }
        $sheets[$sheet.Name] = $rows
    }
    $output = [ordered]@{
        source = [System.IO.Path]::GetFileName($resolvedSource)
        sha256 = (Get-FileHash -LiteralPath $resolvedSource -Algorithm SHA256).Hash.ToLowerInvariant()
        sheets = $sheets
    }
    $output | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $outputPath -Encoding utf8
    Write-Output "Exported $($sheets.Count) sheets to $outputPath"
} finally {
    if ($null -ne $workbook) { $workbook.Close($false) }
    $excel.Quit()
}
