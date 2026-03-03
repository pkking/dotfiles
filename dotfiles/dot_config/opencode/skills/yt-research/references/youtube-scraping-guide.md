# YouTube Scraping Guide (Apify)

## Overview

YouTube data is collected via Apify actors through the native MCP connector. This guide covers the actors, input schemas, and best practices for YouTube scraping.

## Discovering Actors

Before calling any actor, use the Apify MCP tools:

1. `search-actors` with query "YouTube scraper" to find available actors
2. `fetch-actor-details` to get the full input schema and README for a specific actor

Actor availability and schemas can change. Always verify before calling.

## Common YouTube Actors

### YouTube Channel Scraper

Scrapes channel metadata and video listings.

**Typical input:**
```json
{
  "channelUrls": [
    "https://www.youtube.com/@channelname"
  ],
  "maxVideos": 50,
  "sortBy": "date"
}
```

**Typical output fields:**
- `channelName`, `subscriberCount`, `videoCount`
- `videos[]`: `title`, `viewCount`, `likeCount`, `commentCount`, `publishedAt`, `duration`, `url`

### YouTube Video Scraper

Scrapes detailed metadata for specific videos.

**Typical input:**
```json
{
  "startUrls": [
    {"url": "https://www.youtube.com/watch?v=VIDEO_ID"}
  ]
}
```

**Typical output fields:**
- `title`, `description`, `viewCount`, `likeCount`, `commentCount`
- `publishedAt`, `duration`, `tags[]`, `categoryId`

### YouTube Search Scraper

Scrapes YouTube search results for keywords.

**Typical input:**
```json
{
  "searchKeywords": ["claude cowork tutorial", "AI tools for business"],
  "maxResults": 20
}
```

**Typical output fields:**
- `title`, `url`, `channelName`, `viewCount`, `publishedAt`

## Timeout Handling

The Apify MCP connector has a ~30 second timeout. For scraping jobs with many URLs:

1. Call `call-actor` — may timeout for large jobs
2. Timeout does NOT mean failure. The run continues on Apify's servers.
3. Poll `get-actor-run` every 15-30 seconds until status is "SUCCEEDED"
4. Fetch results with `get-actor-output` or `get-dataset-items`

## Pagination

For large datasets, use `offset` and `limit` parameters with `get-dataset-items`:

```
offset: 0, limit: 100   → items 0-99
offset: 100, limit: 100 → items 100-199
```

Save each page to disk before fetching the next.

## Data Persistence

**CRITICAL:** Save all fetched data to JSON files immediately. Context compaction will lose data held only in conversation.

Naming convention:
- `channel_data.json` — raw channel scrape results
- `video_data.json` — raw video scrape results
- `search_results.json` — raw search results

## Rate Limits

- Don't fire multiple Apify runs simultaneously unless needed
- Batch all URLs into a single actor call where possible
- Allow 15-30 seconds between polling requests
