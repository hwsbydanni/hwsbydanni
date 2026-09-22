# Service photos

One photo per bookable service, named by its Acuity appointment type id
(`95263986.jpg`). The category pages show it inside the expanded service row.

These are not committed by hand. Fetch them from Acuity, where Danni already
uploads a photo against each appointment type:

```bash
python3 tools/fetch_service_photos.py           # download what is missing
python3 tools/fetch_service_photos.py --check   # report, download nothing
python3 tools/fetch_service_photos.py --force   # re-download everything
```

The script converts to JPEG, resizes to 800px wide and recompresses, which is
twice the widest the layout ever shows them.

`tools/service-photos.json` records which services have a photo and where it
lives on Acuity's CDN. After adding photos in Acuity, rebuild it with
`--refresh-manifest` and an API key from Acuity's Integrations → API page.

If a file here is missing the page simply shows no photo for that row, so the
site is never broken by one that has not been fetched.
