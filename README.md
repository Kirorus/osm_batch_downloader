# OSM Batch Admin Boundaries Downloader

Сервис для пакетной выгрузки административных границ из OSM (Overpass) с выбором объектов на карте, кэшированием геометрии и экспортом в GeoJSON.

## Запуск

```bash
docker compose up -d --build
```

Открыть: `http://localhost:8282`

## Стек

- Frontend: `Svelte` + `MapLibre GL`
- Backend: `FastAPI` + `Shapely`/`GeoPandas`
- Источник данных: `Overpass API`

## Основные сценарии

- `Load Objects` загружает только список объектов (без полной геометрии).
- Геометрия для карты подгружается по требованию (выбор/hover) и кэшируется.
- `scope=world` разрешен только для `admin_level=2`.
- Для `scope=parent` используется выбранный parent relation.

## Карта / подложка

В правом верхнем углу карты есть кнопка выбора подложки (иконка “слои” под кнопками `+ / − / north`).
Выбор сохраняется локально в браузере.

## Переменные окружения (docker-compose)

- `OVERPASS_URL` — URL Overpass API
- `OSM_LAND_POLYGONS_URLS` — URL(ы) архива `land-polygons-split-4326.zip` через запятую
- `DATA_DIR` — рабочая директория данных внутри контейнера (обычно `/data`)

## Структура выходных данных

Данные сохраняются в `data/geojson`:

```text
data/geojson/<scope_key>/admin_level=<N>/
  manifest.json
  stats.json
  osm_source/
    <scope_key>_admin_level_<N>_osm_source.geojson
    objects/
      <english-name>__<ISO2>__r<ID>.geojson
  land_only/                             # если включено Clip to land
    <scope_key>_admin_level_<N>_land_only.geojson
    objects/
      <english-name>__<ISO2>__r<ID>.geojson
```

Примеры `scope_key`:

- `world_GLOBAL_r0`
- `england_GB_r62149`

Правила имени объекта:

- сначала английское имя (`name:en`, затем fallback),
- затем `ISO2` (если нет — `xx`),
- затем `r<ID>` для стабильной уникальности.

## Кэширование

- Каталог/поиск: `data/cache/catalog`
- Превью-кэш Overpass: `data/cache/preview` (fallback-слой)
- Основной кэш геометрии для экспорта: `data/geojson/.../osm_source/objects`

Если включен `Force refresh OSM source`, экспорт игнорирует существующие объектные файлы и запрашивает геометрию заново.

## Land polygons (опционально)

При включении `Clip to land` сервис использует архив land-polygons.
Если файла нет в кэше, он скачивается автоматически с отображением прогресса в UI.

## Прогресс и ошибки экспорта

- В процессе показываются этапы и текущая фаза обработки объекта (`fetch/build/write/clip`).
- В конце, если есть ошибки, выводится список проблемных объектов (`relation id`, имя, причина).
- Это помогает быстро понять, какие relation не экспортировались и почему.

