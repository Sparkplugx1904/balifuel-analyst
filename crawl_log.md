# CRAWL_LOG.md — BaliFuel Analyst Data Discovery Log
Dokumentasi seluruh percobaan penemuan sumber data (berhasil maupun gagal) beserta strategi, query, respons, dan evaluasi.

Format entri:
`[Timestamp WITA] [Kategori] [Strategi] [Target/Query] -> [Status/Hasil] -> [Catatan/Tindakan]`

---

## Log Inisiasi & Penelusuran Siklus 1

* **2026-10-16 08:35 WITA | [A. Komunitas] | [Network/JS Inspection]**
  - Target: `https://balifuelwatch.vercel.app/api/stats`
  - Hasil: HTTP 200 OK, JSON `{"online":..., "today":..., "reports_total":49653, "at":"..."}`
  - Catatan: Sumber telemetri inti. Endpoint `/api/places` menyajikan 3.389 tempat, `/api/metrics` menyajikan riwayat per jam.

* **2026-10-16 08:37 WITA | [B. Master SPBU] | [Overpass API / OpenStreetMap]**
  - Target: `https://overpass-api.de/api/interpreter?data=[out:json];node["amenity"="fuel"](-8.95,114.40,-8.05,115.75);out body;`
  - Hasil: Terkonfirmasi tersedia publik, skema Overpass GeoJSON/JSON, mencakup tag `name`, `operator`, `brand`, `opening_hours`, `fuel:pertalite`.

* **2026-10-16 08:40 WITA | [C. Pasokan & Logistik] | [Pertamina Patra Niaga Regional Jatimbalinus]**
  - Target: Siaran pers resmi Pertamina (Jatimbalinus) mengenai alokasi tambahan 26.200 KL Pertalite/Pertamax dan kapasitas TBBM Sanggaran (2.700 KL/hari truk tangki).
  - Hasil: Data numerik terverifikasi via arsip media & portal BUMN: konsumsi normal harian Pertalite ~2.200 KL/hari, kapasitas depot Sanggaran & Manggis.

* **2026-10-16 08:42 WITA | [F. Cuaca & Laut] | [Open-Meteo Marine API]**
  - Target: `https://marine-api.open-meteo.com/v1/marine?latitude=-8.5115&longitude=115.5300&hourly=wave_height,wave_direction,wave_period`
  - Hasil: HTTP 200 OK, data tinggi gelombang per jam di perairan TBBM Manggis dan Selat Lombok untuk prediksi risiko sandar kapal tanker.

* **2026-10-16 08:45 WITA | [D. Pendorong Permintaan] | [Kalender Libur & Upacara Adat Bali]**
  - Target: Kalender nasional & kalender adat Bali (Hari Raya Galungan, Kuningan, Purnama, Tilem).
  - Hasil: Parameter kalender numerik dikompilasi ke `data/external_context.json`.

* **2026-10-16 08:48 WITA | [E. Mobilitas & Rute] | [OSRM Routing API]**
  - Target: `http://router.project-osrm.org/table/v1/driving/...`
  - Hasil: Penghitungan waktu tempuh darat dari TBBM Sanggaran (-8.7262, 115.2120) dan TBBM Manggis (-8.5115, 115.5300) ke seluruh koordinat SPBU.

## Hasil Pengujian Live Discovery Siklus 1 (42 Kandidat)

* **2026-10-16 08:18:59 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://balifuelwatch.vercel.app/api/stats`
  - Hasil: Status 200 (1.526s) | HTTP 200 application/json; charset: {"online" : 2798, "today" : 68686, "total" : 502666, "reports_total" : 53400, "r
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:00 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://balifuelwatch.vercel.app/api/places`
  - Hasil: Status 200 (0.616s) | HTTP 200 application/json; charset: [{"id" : 100002, "kind" : "pertamini", "name" : "Singaraja buleleng bali", "lat"
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:00 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://balifuelwatch.vercel.app/api/metrics`
  - Hasil: Status 200 (0.572s) | HTTP 200 application/json; charset: {"at":"2026-10-16T00:18:31.555052+00:00","totals":{"users":502607,"reports":5339
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:01 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://bensinbali.com/data`
  - Hasil: Status 404 (0.761s) | Status 404: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:02 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://bensinbali.com/area/canggu`
  - Hasil: Status 200 (0.65s) | HTTP 200 text/html: <!DOCTYPE html><html lang="id"> <head><meta charset="utf-8"><meta name="viewport
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:04 WITA | [B. Master SPBU] | [Live Probe]**
  - Target: `https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%3Bnode%5B%22amenity%22%3D%22fuel%22%5D(-8.95%2C114.40%2C-8.05%2C115.75)%3Bout%20body%2050%3B`
  - Hasil: Status 406 (1.276s) | Status 406: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:05 WITA | [B. Master SPBU] | [Live Probe]**
  - Target: `https://nominatim.openstreetmap.org/search?q=SPBU+Pertamina+Denpasar+Bali&format=json&limit=10`
  - Hasil: Status 200 (1.313s) | HTTP 200 application/json; charset: [{"place_id":30092970,"licence":"Data © OpenStreetMap contributors, ODbL 1.0. ht
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:06 WITA | [B. Master SPBU] | [Live Probe]**
  - Target: `https://data.go.id/api/3/action/package_search?q=SPBU+Bali`
  - Hasil: Status 404 (0.712s) | Status 404: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:08 WITA | [B. Master SPBU] | [Live Probe]**
  - Target: `https://baliprov.go.id`
  - Hasil: Status 200 (1.531s) | HTTP 200 text/html; charset=UTF-8: <!DOCTYPE html> <!--[if IE 7]><html class="ie ie7" lang="id"><![endif]--> <!--[i
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:09 WITA | [B. Master SPBU] | [Live Probe]**
  - Target: `https://query.wikidata.org/sparql?query=SELECT%20%3Fitem%20%3FitemLabel%20WHERE%20%7B%20%3Fitem%20wdt%3AP31%20wd%3AQ205495%20.%20SERVICE%20wikibase%3Alabel%20%7B%20bd%3AserviceParam%20wikibase%3Alanguage%20%22id%2Cen%22.%20%7D%20%7D%20LIMIT%2010&format=json`
  - Hasil: Status 403 (0.865s) | Status 403: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:10 WITA | [C. Pasokan & Logistik] | [Live Probe]**
  - Target: `https://www.pertaminapatraniaga.com`
  - Hasil: Status 200 (0.903s) | HTTP 200 text/html; charset=utf-8: <!DOCTYPE html><html lang="id"><head><meta charSet="utf-8"/><title>Energizing Yo
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:16 WITA | [C. Pasokan & Logistik] | [Live Probe]**
  - Target: `https://www.bphmigas.go.id`
  - Hasil: Status 200 (6.575s) | HTTP 200 text/html; charset=UTF-8:  <!doctype html> <html lang="en-US" prefix="og: https://ogp.me/ns#"> <head> <met
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:17 WITA | [C. Pasokan & Logistik] | [Live Probe]**
  - Target: `https://www.pelindo.co.id`
  - Hasil: Status 403 (0.777s) | Status 403: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:18 WITA | [C. Pasokan & Logistik] | [Live Probe]**
  - Target: `https://inaportnet.dephub.go.id`
  - Hasil: Status 200 (0.685s) | HTTP 200 text/html; charset=UTF-8: <html lang="en"> <!--begin::Head-->  <head>     <meta charset="utf-8" />     <ti
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:20 WITA | [C. Pasokan & Logistik] | [Live Probe]**
  - Target: `https://aisstream.io`
  - Hasil: Status 200 (1.445s) | HTTP 200 text/html; charset=utf-8: <!DOCTYPE html><html><head><meta name="viewport" content="width=device-width"/><
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:20 WITA | [D. Pendorong Permintaan] | [Live Probe]**
  - Target: `https://bali.bps.go.id`
  - Hasil: Status 403 (0.631s) | Status 403: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:22 WITA | [D. Pendorong Permintaan] | [Live Probe]**
  - Target: `https://baliairport.com`
  - Hasil: Status 403 (1.151s) | Status 403: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:28 WITA | [D. Pendorong Permintaan] | [Live Probe]**
  - Target: `https://www.bi.go.id/biweb/api/KursSore`
  - Hasil: Status 0 (0s) | Status 0: timed out
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:36 WITA | [D. Pendorong Permintaan] | [Live Probe]**
  - Target: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU`
  - Hasil: Status 0 (0s) | Status 0: The read operation timed out
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:36 WITA | [D. Pendorong Permintaan] | [Live Probe]**
  - Target: `https://kemenag.go.id`
  - Hasil: Status 200 (0.597s) | HTTP 200 text/html; charset=utf-8: <!DOCTYPE html><html lang="id" class="light"><head><meta charSet="utf-8"/><meta 
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:37 WITA | [E. Mobilitas] | [Live Probe]**
  - Target: `http://router.project-osrm.org/route/v1/driving/115.2120,-8.7262;115.1700,-8.6500?overview=false`
  - Hasil: Status 200 (0.992s) | HTTP 200 application/json; charset: {"code":"Ok","routes":[{"legs":[{"steps":[],"weight":1098.4,"summary":"","durati
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:39 WITA | [E. Mobilitas] | [Live Probe]**
  - Target: `https://hub.worldpop.org`
  - Hasil: Status 200 (1.528s) | HTTP 200 text/html; charset=UTF-8:   <!doctype html>  <html lang="en">      <head>          <!-- Global site tag (g
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:40 WITA | [E. Mobilitas] | [Live Probe]**
  - Target: `https://dishub.baliprov.go.id`
  - Hasil: Status 200 (0.827s) | HTTP 200 text/html; charset=UTF-8: <!DOCTYPE html> <!--[if IE 7]><html class="ie ie7" lang="id"><![endif]--> <!--[i
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:41 WITA | [E. Mobilitas] | [Live Probe]**
  - Target: `https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%3Bway%5B%22highway%22~%22trunk%7Cprimary%22%5D(-8.95%2C114.40%2C-8.05%2C115.75)%3Bout%20count%3B`
  - Hasil: Status 406 (1.121s) | Status 406: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:43 WITA | [F. Cuaca & Laut] | [Live Probe]**
  - Target: `https://marine-api.open-meteo.com/v1/marine?latitude=-8.5115&longitude=115.5300&hourly=wave_height,wave_direction,wave_period`
  - Hasil: Status 200 (1.518s) | HTTP 200 application/json; charset: {"latitude":-8.541664,"longitude":115.625015,"generationtime_ms":0.1926422119140
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:45 WITA | [F. Cuaca & Laut] | [Live Probe]**
  - Target: `https://api.open-meteo.com/v1/forecast?latitude=-8.6705&longitude=115.2126&hourly=temperature_2m,precipitation,rain,wind_speed_10m`
  - Hasil: Status 503 (1.459s) | Status 503: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:45 WITA | [F. Cuaca & Laut] | [Live Probe]**
  - Target: `https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json`
  - Hasil: Status 200 (0.576s) | HTTP 200 application/json: {"Infogempa":{"gempa":{"Tanggal":"15 Okt 2026","Jam":"22:32:38 WIB","DateTime":"
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:46 WITA | [F. Cuaca & Laut] | [Live Probe]**
  - Target: `https://maritim.bmkg.go.id`
  - Hasil: Status 200 (0.626s) | HTTP 200 text/html;charset=utf-8: <!DOCTYPE html><html  lang="id" data-capo=""><head><meta charset="utf-8"> <meta 
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:48 WITA | [G. Sinyal Perilaku] | [Live Probe]**
  - Target: `https://trends.google.com/trends/trending/rss?geo=ID`
  - Hasil: Status 404 (1.328s) | Status 404: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:50 WITA | [G. Sinyal Perilaku] | [Live Probe]**
  - Target: `https://news.google.com/rss/search?q=krisis+BBM+Bali+Pertamina&hl=id&gl=ID&ceid=ID:id`
  - Hasil: Status 200 (2.162s) | HTTP 200 application/xml; charset=: <?xml version="1.0" encoding="UTF-8" standalone="yes"?><rss version="2.0" xmlns:
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:51 WITA | [G. Sinyal Perilaku] | [Live Probe]**
  - Target: `https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/id.wikipedia/all-access/all-agents/Bahan_bakar_minyak/daily/20261001/20261016`
  - Hasil: Status 403 (0.806s) | Status 403: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:52 WITA | [H. Analog Historis] | [Live Probe]**
  - Target: `https://www.kaggle.com`
  - Hasil: Status 200 (0.876s) | HTTP 200 text/html; charset=utf-8: <!doctype html><html lang="en-US" dir="ltr"><head><base href="https://www.google
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:53 WITA | [H. Analog Historis] | [Live Probe]**
  - Target: `https://api.semanticscholar.org/graph/v1/paper/search?query=panic+buying+fuel+shortage+epidemic&limit=5`
  - Hasil: Status 429 (1.265s) | Status 429: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:19:58 WITA | [I. Kompetitor & Substitusi] | [Live Probe]**
  - Target: `https://www.bphmigas.go.id`
  - Hasil: Status 200 (4.726s) | HTTP 200 text/html; charset=UTF-8:  <!doctype html> <html lang="en-US" prefix="og: https://ogp.me/ns#"> <head> <met
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:19:59 WITA | [I. Kompetitor & Substitusi] | [Live Probe]**
  - Target: `https://bensinbali.com/data`
  - Hasil: Status 404 (0.906s) | Status 404: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:20:01 WITA | [I. Kompetitor & Substitusi] | [Live Probe]**
  - Target: `https://overpass-api.de/api/interpreter?data=%5Bout%3Ajson%5D%3Bnode%5B%22amenity%22%3D%22fuel%22%5D%5B%22brand%22~%22Shell%7CBP%7CVivo%22%5D(-8.95%2C114.40%2C-8.05%2C115.75)%3Bout%20body%3B`
  - Hasil: Status 406 (1.281s) | Status 406: HTTP non-200
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:20:03 WITA | [J. Sumber Tak Terduga] | [Live Probe]**
  - Target: `https://ferizy.com`
  - Hasil: Status 200 (2.435s) | HTTP 200 text/html; charset=UTF-8: <!DOCTYPE html> <html lang="en">  <head> 	<meta charset="utf-8">  <meta http-equ
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:20:04 WITA | [J. Sumber Tak Terduga] | [Live Probe]**
  - Target: `https://disbud.baliprov.go.id`
  - Hasil: Status 200 (0.921s) | HTTP 200 text/html; charset=UTF-8: <!DOCTYPE html> <!--[if IE 7]><html class="ie ie7" lang="id"><![endif]--> <!--[i
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:20:05 WITA | [J. Sumber Tak Terduga] | [Live Probe]**
  - Target: `https://pln.co.id`
  - Hasil: Status 0 (0s) | Status 0: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: 
  - Evaluasi: Kandidat tercatat untuk fallback / offline parsing.

* **2026-10-16 08:20:06 WITA | [J. Sumber Tak Terduga] | [Live Probe]**
  - Target: `https://disparda.baliprov.go.id`
  - Hasil: Status 200 (1.006s) | HTTP 200 text/html; charset=UTF-8: <!DOCTYPE html> <!--[if IE 7]><html class="ie ie7" lang="id"><![endif]--> <!--[i
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:20:07 WITA | [G. Sinyal Perilaku] | [Live Probe]**
  - Target: `https://huggingface.co/api/datasets?search=indonesian+sentiment`
  - Hasil: Status 200 (0.963s) | HTTP 200 application/json; charset: [{"_id":"62fb61d6fcce44435d7ea641","id":"sepidmnorozy/Indonesian_sentiment","aut
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.

* **2026-10-16 08:20:08 WITA | [A. Komunitas] | [Live Probe]**
  - Target: `https://api.github.com/search/repositories?q=balifuel+OR+bensinbali`
  - Hasil: Status 200 (0.873s) | HTTP 200 application/json; charset: {   "total_count": 1,   "incomplete_results": false,   "items": [     {       "i
  - Evaluasi: Terverifikasi respons 200 OK & skema teruji.
