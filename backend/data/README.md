# Backend data folder

After running the pipeline (`python run_pipeline.py` from the project root),
copy the latest output files here so the backend can serve them in production:

```powershell
# From spotify-review-engine/ project root:
copy data\processed\insights_*.csv     backend\data\
copy outputs\themes_*.json             backend\data\
copy outputs\discovery_insights_report_*.md backend\data\
```

The backend's `data_loader.py` automatically picks the most recent file matching:
- `insights_*.csv`
- `themes_*.json`
- `discovery_insights_report_*.md`

These files **must be committed to git** so Railway can ship them with the deploy.
