# Documented responses of one real analytics API: Ahrefs API v3

Copied from Ahrefs' public documentation on 16 November 2026. The API was not
called. Two sources, both published by Ahrefs:

- the reference pages under https://docs.ahrefs.com/en/api/reference/site-explorer
- the OpenAPI specification https://docs.ahrefs.com/openapi.json (`"version": "3.0.0"`),
  which the reference pages are rendered from

Base URL from the specification: `https://api.ahrefs.com/v3`. Authentication:
`"securitySchemes": {"http": {"type": "http", "scheme": "bearer"}}`; the
reference examples send `Authorization: Bearer $AHREFS_API_KEY`.

The endpoint closest to our stub's `analytics(domain, period)` is
**Site Explorer → Metrics**, `GET /site-explorer/metrics`, required query
parameters `target` ("The target of the search: a domain or a URL.") and
`date` ("A date to report metrics on in YYYY-MM-DD format."). The paged
endpoint used below is **Organic keywords**, `GET /site-explorer/organic-keywords`.

| Response | Status | Copied from the documentation |
| --- | --- | --- |
| Normal answer | documented | example body and field descriptions below |
| Empty answer | not documented | no example of a zero-record response on any Site Explorer page or in the specification |
| Server error | partly | status 500 "Internal Error" with the error schema; no example body |
| Invalid or expired key | partly | status 401 "Unauthorized" and 403 "Forbidden" with the error schema; no example body, no message text |
| Timeout | partly | a `timeout` request parameter is documented; no timeout response is |
| Pagination | not documented for Site Explorer | only `limit`; `offset` exists on three other endpoints of the same API |

## 1. Normal answer

Source: https://docs.ahrefs.com/en/api/reference/site-explorer/get-metrics
(example response, 200 OK) and the schema `site-explorer.metrics` in
https://docs.ahrefs.com/openapi.json.

```json
{
  "metrics": {
    "org_cost": 0,
    "org_keywords": 0,
    "org_keywords_1_3": 0,
    "org_traffic": 0,
    "paid_cost": 0,
    "paid_keywords": 0,
    "paid_pages": 0,
    "paid_traffic": 0
  }
}
```

Field descriptions, word for word from the schema:

| Field | Type | Description |
| --- | --- | --- |
| org_cost | integer, null | (10 units) The estimated value of your target's monthly organic search traffic, in USD cents. |
| org_keywords | integer | The total number of keywords that your target ranks for in the top 100 organic search results. |
| org_keywords_1_3 | integer | The total number of keywords that your target ranks for in the top 3 organic search results. |
| org_traffic | integer | (10 units) The estimated number of monthly visitors that your target gets from organic search. |
| paid_cost | integer, null | (10 units) The estimated cost of your target's monthly paid search traffic, in USD cents. |
| paid_keywords | integer | The total number of keywords that your target ranks for in paid search results. |
| paid_pages | integer | The total number of pages from a target ranking in paid search results. |
| paid_traffic | integer | (10 units) The estimated number of monthly visitors that your target gets from paid search. |

The organic-keywords endpoint answers with `{"keywords": [ ... ]}`, one object
per keyword (about sixty fields, all placeholders in the documented example):
https://docs.ahrefs.com/en/api/reference/site-explorer/get-organic-keywords.

## 2. Empty answer

**Not documented.** Checked: the Metrics page, the Organic keywords page, the
Site Explorer overview (https://docs.ahrefs.com/en/api/reference/site-explorer)
and the specification. The documented examples hold placeholder values (zeros,
`"string"`), not an empty result. By the schema the only shape an empty
organic-keywords answer can take is `{"keywords": []}`; that is an inference
from the schema, not a documented example.

## 3. Server error

Source: https://docs.ahrefs.com/openapi.json, `components.responses` and
`components.schemas`. Status listed on every Site Explorer endpoint: 500.

```json
"site-explorer.error_500": {
  "description": "Internal Error",
  "content": {
    "application/json": {"schema": {"$ref": "#/components/schemas/site-explorer.Error_response"}},
    "application/xml":  {"schema": {"$ref": "#/components/schemas/site-explorer.Error_response"}}
  }
}
```

```json
"site-explorer.Error_response": {
  "properties": {"error": {"type": "string"}},
  "type": "object",
  "xml": {"name": "AhrefsApiResponse"}
}
```

So the body is `{"error": "<string>"}`. **No example body or message text is
documented.** No 502, 503 or 504 is listed. No advice such as "try again later"
appears anywhere in the specification or on the reference pages read.

## 4. Invalid or expired key

Source: https://docs.ahrefs.com/openapi.json. Statuses listed on every Site
Explorer endpoint: 401 and 403, same error schema as above.

```json
"site-explorer.error_401": {"description": "Unauthorized", "content": { ... "site-explorer.Error_response" ... }}
"site-explorer.error_403": {"description": "Forbidden",    "content": { ... "site-explorer.Error_response" ... }}
```

Body shape `{"error": "<string>"}`. **No example body and no message text
documented**, and nothing distinguishes an invalid key from an expired one in
the documentation.

Also listed, same schema, no body: `400` "Bad Request" and `429` "Too Many
Requests". No rate-limit figures or retry guidance are given on the pages
read; the page named "Limits consumption" in the site navigation
(https://docs.ahrefs.com/en/api/docs/limits-consumption) returned 404 when
fetched.

## 5. Timeout

Source: https://docs.ahrefs.com/en/api/reference/site-explorer/get-organic-keywords
and the specification. A request parameter only:

```json
{"name": "timeout", "in": "query", "required": false,
 "description": "A manual timeout duration in seconds.",
 "schema": {"type": "integer", "minimum": 0}}
```

**What the API returns when a request times out is not documented**: no status
code, no body. The Metrics endpoint has no timeout parameter.

## 6. Pagination

Source: the specification. On Site Explorer endpoints the only related
parameter is

```json
{"name": "limit", "in": "query", "required": false,
 "description": "The number of results to return.",
 "schema": {"type": "integer", "minimum": 1, "default": 1000}}
```

**No cursor, offset, page or next-page field is documented for any Site
Explorer endpoint**, so a second page cannot be requested there. Three other
endpoints of the same API (`/site-audit/page-explorer`,
`/keywords-explorer/volume-by-country`, `/social-media/posts`) take

```json
{"name": "offset", "description": "The number of results to skip.",
 "schema": {"type": "integer", "default": 0}}
```

together with `limit`, which is the API's only documented paging mechanism.
No response field announces whether more results exist.

## What this means for the stub

Three things in our stub have no documented counterpart at Ahrefs: the empty
answer, the error message texts, and cursor paging (scenario 5). The error
*shape* is documented, `{"error": "<string>"}`, and so are the status codes
401, 403, 429 and 500. A stub that wants to look like Ahrefs should use that
shape and those codes and leave the message text short, since the
documentation gives none.
