foreach ($i in 0..6) {
    $chunkFile = "..\data_dump_chunk_$i.json"
    Write-Host "Loading $chunkFile..."
    python manage.py loaddata -v 2 $chunkFile
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error loading $chunkFile. Stopping."
        exit $LASTEXITCODE
    }
}
Write-Host "All chunks loaded successfully!"
