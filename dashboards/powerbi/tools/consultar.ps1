# Roda uma consulta DAX no Power BI Desktop aberto e imprime o resultado em JSON.
# Uso: powershell -File tools\consultar.ps1 -DaxArquivo consulta.dax
param([string]$DaxArquivo)
$Dax = Get-Content $DaxArquivo -Raw -Encoding UTF8
$pbi = (Get-AppxPackage -Name "*PowerBIDesktop*").InstallLocation
Add-Type -Path "$pbi\bin\Microsoft.PowerBI.AdomdClient.dll"
$proc = Get-Process msmdsrv -ErrorAction Stop | Sort-Object StartTime -Descending | Select-Object -First 1
$Porta = (Get-NetTCPConnection -OwningProcess $proc.Id -State Listen | Select-Object -First 1).LocalPort
$con = New-Object Microsoft.AnalysisServices.AdomdClient.AdomdConnection("Data Source=localhost:$Porta")
$con.Open()
$cmd = $con.CreateCommand(); $cmd.CommandText = $Dax
$r = $cmd.ExecuteReader(); $linhas = @()
while ($r.Read()) { $o = [ordered]@{}; for ($i = 0; $i -lt $r.FieldCount; $i++) { $o[$r.GetName($i)] = $r.GetValue($i) }; $linhas += [pscustomobject]$o }
$r.Close(); $con.Close()
ConvertTo-Json -InputObject @($linhas) -Depth 3
